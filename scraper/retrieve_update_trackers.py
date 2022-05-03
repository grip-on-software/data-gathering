"""
Script to retrieve update tracker files from the database for synchronization.

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
import logging
import sys
from typing import Optional, Set, Type
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.update import Update_Tracker, Database_Tracker, SSH_Tracker

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Retrieve the update trackers')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path of the private key')
    parser.add_argument('--user', default=config.get('database', 'username'),
                        help='username to connect to the database with')
    parser.add_argument('--password', default=config.get('database', 'password'),
                        help='password to connect to the database with')
    parser.add_argument('--host', default=config.get('database', 'host'),
                        help='host name of the database to connect to')
    parser.add_argument('--database', default=config.get('database', 'name'),
                        help='database name to retrieve from')
    parser.add_argument('--agent', default=config.get('ssh', 'username'),
                        help='agent username for the ssh source')
    parser.add_argument('--server', default=config.get('ssh', 'host'),
                        help='host name of the ssh source')
    parser.add_argument('--files', nargs='+',
                        help='update tracker files to consider for updates')
    parser.add_argument('--skip', action='store_true', default=False,
                        help='Do not retrieve trackers but remove local files')

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def build_tracker(args: Namespace, project: Project) -> Update_Tracker:
    """
    Build an update tracker source object based on the arguments.
    """

    tracker_class: Type[Update_Tracker] = Update_Tracker
    if args.agent and args.server:
        tracker_class = SSH_Tracker
        options = {
            'user': args.agent,
            'host': args.server,
            'key_path': args.path
        }
    else:
        tracker_class = Database_Tracker
        options = {
            'user': args.user,
            'password': args.password,
            'host': args.host,
            'database': args.database
        }

    return tracker_class(project, **options)

def remove_files(files: Optional[Set[str]], project: Project) -> None:
    """
    Remove stale update tracker files that are not used during the scrape.
    """

    if files is not None:
        for filename in files:
            path = project.export_key / filename
            if path.exists():
                path.unlink()

def main() -> int:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    project.make_export_directory()

    # Convert to set for easier file name comparisons in some tracker sources
    files: Optional[Set[str]] = None
    if args.files is not None:
        files = set(args.files)

    if args.skip:
        logging.warning('Skipping update trackers for project %s', args.project)
        remove_files(files, project)
    else:
        tracker = build_tracker(args, project)
        try:
            tracker.retrieve(files=files)
        except RuntimeError:
            logging.exception('Could not retrieve update trackers for project %s',
                              args.project)
            return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
