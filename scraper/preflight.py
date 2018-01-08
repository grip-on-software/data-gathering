"""
Perform pre-flight checks for the Docker agent scraper.
"""

import argparse
from datetime import datetime
import json
import logging
import os
import sys
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session
from gatherer.utils import format_date

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Perform pre-flight checks')
    parser.add_argument('project', help='project key to check for')
    parser.add_argument('--secrets', default='secrets.json',
                        help='Path to the secrets file')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to check')
    parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                        help='Do not check controller API host')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')
    parser.add_argument('--skip', action='store_true', dest='skip',
                        default=False, help='Skip the actual preflight checks')
    Log_Setup.add_argument(parser)

    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def check_secrets(filename):
    """
    Check whether the secrets file contains all required options.
    """

    with open(filename) as secrets_file:
        secrets = json.load(secrets_file)
        if 'salts' in secrets:
            if 'salt' in secrets['salts'] and 'pepper' in secrets['salts']:
                return True

        logging.critical('Secrets file %s does not contain salt and pepper',
                         filename)
        return False

def check_controller(host, cert, project):
    """
    Check availability of the controller API host and services.
    """

    url = 'https://{}/auth/status.py?project={}'.format(host, project.jira_key)
    request = Session(verify=cert).get(url)

    try:
        response = json.loads(request.text)
    except ValueError:
        logging.exception('Invalid JSON response from controller API: %s',
                          request.text)
        return False

    if Session.is_code(request, 'service_unavailable') and 'total' in response:
        problems = []
        for key, value in list(response.keys()):
            if key != 'total' and not value['ok']:
                message = value['message'] if 'message' in value else 'Not OK'
                problems.append("Status '{}': {}".format(key, message))

        logging.warning('Controller status: %s: %s',
                        response['total']['message'], ', '.join(problems))
        return False

    if not Session.is_code(request, 'ok'):
        logging.critical('Unexpected HTTP error %d for controller status',
                         request.status_code, extra=response)
        return False

    return True

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    # Perform pre-flight checks for Docker agent:
    # - Do we have a populated secrets file?
    # - Does the controller API indicate that all is OK?

    if not args.skip:
        if not os.path.exists(args.secrets):
            logging.critical('Secrets file %s is not available', args.secrets)
            return 1

        if not check_secrets(args.secrets):
            return 1

        if args.ssh and not check_controller(args.ssh, args.cert, project):
            return 1

    project.make_export_directory()
    date_filename = os.path.join(project.export_key, 'preflight_date.txt')
    with open(date_filename, 'w') as date_file:
        date_file.write(format_date(datetime.now()))

    return 0

if __name__ == '__main__':
    sys.exit(main())