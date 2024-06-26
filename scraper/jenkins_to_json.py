"""
Script to obtain statistics from a Jenkins instance.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from argparse import ArgumentParser, Namespace
from configparser import RawConfigParser
import json
import logging
from pathlib import Path
from typing import Optional, Union
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain import source
from gatherer.jenkins import Jenkins
from gatherer.log import Log_Setup

def parse_args(config: RawConfigParser) -> Namespace:
    """
    Parse command line arguments.
    """

    verify_config = config.get('jenkins', 'verify')
    verify: Union[str, bool] = verify_config
    if not Configuration.has_value(verify_config):
        verify = False
    elif not Path(verify_config).exists():
        verify = True

    username: Optional[str] = config.get('jenkins', 'username')
    password: Optional[str] = config.get('jenkins', 'password')
    if not Configuration.has_value(username):
        username = None
        password = None

    description = "Obtain Jenkins usage statistics"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument('--host', default=config.get('jenkins', 'host'),
                        help='Base URL of the Jenkins instance')
    parser.add_argument('--username', default=username,
                        help='Username to log into the Jenkins instance')
    parser.add_argument('--password', default=password,
                        help='Password to log into the Jenkins instance')
    parser.add_argument('--verify', nargs='?', const=True, default=verify,
                        help='Enable SSL cerificate verification')
    parser.add_argument('--no-verify', action='store_false', dest='verify',
                        help='Disable SSL cerificate verification')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    config = Configuration.get_settings()
    args = parse_args(config)
    project = Project(args.project)
    try:
        if Configuration.has_value(args.host):
            jenkins = Jenkins(args.host,
                              username=args.username,
                              password=args.password,
                              verify=args.verify)
        else:
            jenkins_source = project.sources.find_source_type(source.Jenkins)
            if not jenkins_source:
                logging.warning('Project %s has no Jenkins instance configured',
                                project.key)
                return

            jenkins = jenkins_source.jenkins_api
    except (RuntimeError, ConnectError, HTTPError, Timeout):
        logging.exception('Could not log in to Jenkins')
        return

    try:
        data = {
            'host': jenkins.base_url,
            'jobs': len(jenkins.jobs),
            'views': len(jenkins.views),
            'nodes': len(jenkins.nodes)
        }
    except (ConnectError, HTTPError, Timeout):
        logging.exception('Could not receive data from Jenkins')
        return

    export_path = project.export_key / 'data_jenkins.json'
    with export_path.open('w', encoding='utf-8') as export_file:
        json.dump(data, export_file)

if __name__ == "__main__":
    main()
