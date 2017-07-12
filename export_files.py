"""
Script to export the export and update files to the controller server.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import subprocess
import requests
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Export data and update files')
    parser.add_argument('project', help='project key to export')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path of the private key')
    parser.add_argument('--agent', default=config.get('ssh', 'username'),
                        help='agent username for the ssh source')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='host name of the ssh server')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of the ssh server')
    parser.add_argument('--update', nargs='+', default=[],
                        help='update tracker files to consider')
    parser.add_argument('--export', nargs='+', default=[],
                        help='data files to consider for export')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def export_file(project, export_path, filename, key_path):
    """
    Upload the export data file `filename` from the export directory for the
    `project` to a remote SCP directory indicated by the `export_path`, using
    the identity file in `key_path` for SSH public key authentication.
    """

    subprocess.call([
        'scp', '-i', key_path,
        '{}/{}'.format(project.export_key, filename),
        '{}/{}'.format(export_path, filename)
    ])

def update_controller(host, project, cert):
    """
    Indicate to the controller host that we are done with exporting the current
    state of the gatherer.
    """

    url = 'https://{}/auth/export.py?project={}'.format(host, project.jira_key)
    request = requests.post(url, verify=cert)

    if request.status_code != requests.codes['ok']:
        raise RuntimeError('HTTP error {}: {}'.format(request.status_code, request.text))

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    auth = args.agent + '@' + args.ssh
    path = '{}:~/{}'.format(auth, project.export_key)

    for filename in args.export + args.update:
        export_file(project, path, filename, args.path)

    update_controller(args.ssh, project, args.cert)

if __name__ == "__main__":
    main()
