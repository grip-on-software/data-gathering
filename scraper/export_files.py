"""
Script to export the export and update files to the controller server.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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
import socket
import subprocess
import sys
from typing import Optional, Sequence
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Export data and update files')
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
    parser.add_argument('--other', nargs='+', default=[],
                        help='paths to other files to consider for export')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                        default=False, help='Log actions rather than executing')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

class Exporter:
    """
    Export data collected for one project to the controller.
    """

    def __init__(self, project: Project, host: str, agent: str,
                 dry_run: bool = False) -> None:
        self.project = project
        self.host = host
        self.agent = agent
        self.dry_run = dry_run

    def export_files(self, key_path: str, filenames: Sequence[str],
                     paths: Sequence[str]):
        """
        Upload the export data files `filenames` for the project from the
        export directory for the project to a remote SCP directory indicated
        by the `export_path`, using the identity file in `key_path` for SSH
        public key authentication.

        If `dry_run` is `True`, then only log what command would be executed
        rather than performing this action.
        """

        export_path = f'{self.agent}{"@"}{self.host}:~/{self.project.export_key}/'

        args = ['scp', '-i', key_path] + [
            f'{self.project.export_key}/{filename}' for filename in filenames
        ]
        args.extend(list(paths))
        args.append(export_path)
        if self.dry_run:
            logging.info('Dry run: Would execute %s', ' '.join(args))
        else:
            try:
                output = subprocess.check_output(args, stderr=subprocess.STDOUT)
                if output:
                    logging.info('SSH: %s', output.decode('utf-8').rstrip())
            except subprocess.CalledProcessError as error:
                logging.info('SSH: %s', error.output.decode('utf-8').rstrip())
                if b'No such file or directory' not in error.output:
                    raise RuntimeError('Could not export files') from error

    def update_controller(self, cert: str,
                          export: Optional[Sequence[str]] = None,
                          update: Optional[Sequence[str]] = None,
                          other: Optional[Sequence[str]] = None) -> None:
        """
        Indicate to the controller API that we are done with exporting
        the current state of the gatherer for the project.

        Use `cert` to validate the HTTPS connection to the controller.

        If `dry_run` is `True`, then only log what URL would be requested
        rather than performing this action.

        If the requested URL returns a different status code than
        '202 Accepted', then a `RuntimeError` is raised.
        """

        url = f'https://{self.host}/auth/export.py?project={self.project.jira_key}'
        if self.dry_run:
            logging.info('Dry run: Would send a POST request to %s', url)
            return

        agent_key = Configuration.get_agent_key()

        session = Session(verify=cert)
        request = session.post(url, data={
            "files": json.dumps({
                "export": export,
                "update": update,
                "other": other,
            }),
            "agent": json.dumps({
                "user": self.agent,
                "key": agent_key,
                "hostname": socket.gethostname(),
                "version": session.headers['User-Agent']
            })
        })

        if not Session.is_code(request, 'accepted'):
            raise RuntimeError(f'HTTP error {request.status_code}: {request.text}')

def main() -> int:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    if not Configuration.has_value(args.ssh):
        logging.critical('No SSH export host defined, cannot export data.')
        return 1

    exporter = Exporter(project, args.ssh, args.agent, dry_run=args.dry_run)

    try:
        exporter.export_files(args.path, args.export + args.update, args.other)
    except RuntimeError:
        logging.exception('Could not export data and update/auxiliary files')
        return 1

    if args.export or args.update:
        try:
            exporter.update_controller(args.cert,
                                       export=args.export,
                                       update=args.update,
                                       other=args.other)
        except RuntimeError:
            logging.exception('Could not notify the export controller')
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
