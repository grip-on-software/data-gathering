"""
Perform pre-flight checks for the Docker agent scraper.
"""

import argparse
from datetime import datetime
import json
import logging
import os
import sys
import requests
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
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
    request = requests.get(url, verify=cert)

    try:
        response = json.loads(request.text)
    except ValueError:
        logging.exception('Invalid JSON response from controller API: %s',
                          request.text)
        return False

    if request.status_code != requests.codes['ok']:
        logging.critical('HTTP error %d for controller status',
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

    if not os.path.exists(args.secrets):
        logging.critical('Secrets file %s is not available', args.secrets)
        return 1

    if not check_secrets(args.secrets):
        return 1

    if args.ssh and not check_controller(args.ssh, args.cert, project):
        return 1

    date_filename = os.path.join(project.export_key, 'preflight_date.txt')
    with open(date_filename, 'w') as date_file:
        date_file.write(format_date(datetime.now()))

    return 0

if __name__ == '__main__':
    sys.exit(main())
