"""
Script to export the export and update files to the controller server.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import logging
import subprocess
import sys
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session

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
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                        default=False, help='Log actions rather than executing')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def export_files(project, key_path, filenames, export_path, dry_run=False):
    """
    Upload the export data files `filenames` for the project `project` from
    the export directory for the `project` to a remote SCP directory indicated
    by the `export_path`, using the identity file in `key_path` for SSH public
    key authentication.

    If `dry_run` is `True`, then only log what command would be executed rather
    than performing this action.
    """

    args = ['scp', '-i', key_path] + [
        '{}/{}'.format(project.export_key, filename) for filename in filenames
    ] + [export_path + '/']
    if dry_run:
        logging.info('Dry run: Would execute %s', ' '.join(args))
    else:
        subprocess.call(args)

def update_controller(host, project, cert, dry_run=False):
    """
    Indicate to the controller API at domain `host` that we are done with
    exporting the current state of the gatherer for the project `project`.

    Use the certificate `cert` to verify the controller API.

    If `dry_run` is `True`, then only log what URL would be requested rather
    than performing this action.

    If the requested URL returns a different status code than '202 Accepted',
    then a `RuntimeError` is raised.
    """

    url = 'https://{}/auth/export.py?project={}'.format(host, project.jira_key)
    if dry_run:
        logging.info('Dry run: Would send a POST request to %s', url)
        return

    request = Session(verify=cert).post(url)

    if not Session.is_code(request, 'accepted'):
        raise RuntimeError('HTTP error {}: {}'.format(request.status_code, request.text))

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    if not Configuration.has_value(args.ssh):
        logging.critical('No SSH export host defined, cannot export data.')
        return 1

    auth = args.agent + '@' + args.ssh
    path = '{}:~/{}'.format(auth, project.export_key)

    export_files(project, args.path, args.export + args.update, path,
                 dry_run=args.dry_run)

    try:
        update_controller(args.ssh, project, args.cert, dry_run=args.dry_run)
    except RuntimeError:
        logging.exception('Could not notify the export controller')
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
