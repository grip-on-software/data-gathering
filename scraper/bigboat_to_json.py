"""
Script to retrieve current details of the state of a BigBoat host.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University

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
import json
import logging

from bigboat import Client_v2

from gatherer.bigboat import Statuses
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain current state of a BigBoat host'
    parser = ArgumentParser(description=description)
    parser.add_argument('project', help='project key')
    parser.add_argument('--host', help='BigBoat instance URL')
    parser.add_argument('--key', help='BigBoat instance API key')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to upload status to')
    parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                        help='Do not upload status to controller API host')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()

    project_key = str(args.project)
    project = Project(project_key)

    if args.host is not None:
        host = str(args.host)
    else:
        host = project.get_key_setting('bigboat', 'host')
        if not Configuration.has_value(host):
            logging.warning('No BigBoat host defined for %s', project_key)
            return

    if args.key is not None:
        key = str(args.key)
    else:
        key = project.get_key_setting('bigboat', 'key')
        if not Configuration.has_value(key):
            logging.warning('No BigBoat API key defined for %s', project_key)
            return

    client = Client_v2(host, api_key=key)
    with Statuses.from_api(project, client.statuses()) as statuses:
        output = statuses.export()

    if args.ssh:
        url = f'https://{args.ssh}/auth/status.py?project={project.jira_key}'
        data = {
            'status': json.dumps(output),
            'source': host
        }
        request = Session(verify=args.cert).post(url, data=data)
        if not Session.is_code(request, 'accepted'):
            raise RuntimeError(f'HTTP error {request.status_code}: {request.text}')
    else:
        data_path = project.export_key / 'data_bigboat.json'
        with data_path.open('w', encoding='utf-8') as data_file:
            json.dump(output, data_file, indent=4)

if __name__ == '__main__':
    main()
