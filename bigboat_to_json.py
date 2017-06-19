"""
Script to retrieve current details of the state of a BigBoat host.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import json
import logging
import os.path

from bigboat import Client_v2
import requests

from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.utils import parse_date

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain current state of a BigBoat host'
    parser = argparse.ArgumentParser(description=description)
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

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key)

    if args.host is not None:
        host = args.host
    else:
        host = project.get_key_setting('bigboat', 'host')
        if not Configuration.has_value(host):
            logging.warning('No BigBoat host defined for %s', project_key)

    if args.key is not None:
        key = args.key
    else:
        key = project.get_key_setting('bigboat', 'key')
        if not Configuration.has_value(key):
            logging.warning('No BigBoat API key defined for %s', project_key)

    client = Client_v2(host, api_key=key)
    statuses = client.statuses()

    output = []
    for status in statuses:
        output.append({
            'name': status['name'],
            'checked_time': parse_date(status['lastCheck']['ISO']),
            'ok': '1' if status['isOk'] else '0'
        })

    if args.ssh:
        url = 'https://{}/auth/status.py?project={}'.format(args.ssh,
                                                            project.jira_key)
        request = requests.post(url, data={'status': json.dumps(output)},
                                verify=args.cert)
        if request.status_code != requests.codes['accepted']:
            raise RuntimeError('HTTP error {}: {}'.format(request.status_code,
                                                          request.text))
    else:
        data_path = os.path.join(project.export_key, 'data_bigboat.json')
        with open(data_path, 'w') as data_file:
            json.dump(output, data_file, indent=4)

if __name__ == '__main__':
    main()
