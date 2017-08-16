"""
Script to obtain statistics from a Jenkins instance.
"""

import argparse
import json
import logging
import os.path
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.jenkins import Jenkins
from gatherer.log import Log_Setup

def parse_args(config):
    """
    Parse command line arguments.
    """

    verify = config.get('jenkins', 'verify')
    if not Configuration.has_value(verify):
        verify = False
    elif not os.path.exists(verify):
        verify = True

    username = config.get('jenkins', 'username')
    password = config.get('jenkins', 'password')
    if not Configuration.has_value(username):
        username = None
        password = None

    description = "Obtain Jenkins usage statistics"
    parser = argparse.ArgumentParser(description=description)
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

def main():
    """
    Main entry point.
    """

    config = Configuration.get_settings()
    args = parse_args(config)
    project = Project(args.project)
    if not Configuration.has_value(args.host):
        logging.warning('Project %s has no Jenkins instance configured',
                        project.key)
        return

    jenkins = Jenkins(args.host, username=args.username, password=args.password,
                      verify=args.verify)

    data = {
        'host': jenkins.base_url,
        'jobs': len(jenkins.jobs),
        'views': len(jenkins.views),
        'nodes': len(jenkins.nodes)
    }

    export_filename = os.path.join(project.export_key, 'data_jenkins.json')
    with open(export_filename, 'w') as export_file:
        json.dump(data, export_file)

if __name__ == "__main__":
    main()
