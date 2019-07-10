"""
Script to retrieve update tracker files from the database for synchronization.
"""

import argparse
import logging
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.update import Database_Tracker, SSH_Tracker

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Retrieve the update trackers')
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

def build_tracker(args, project):
    """
    Build an update tracker source object based on the arguments.
    """

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

def remove_files(files, project):
    """
    Remove stale update tracker files that are not used during the scrape.
    """

    if files is not None:
        for filename in files:
            path = project.export_key / filename
            if path.exists():
                path.unlink()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    project.make_export_directory()

    # Convert to set for easier file name comparisons in some tracker sources
    if args.files is None:
        files = None
    else:
        files = set(args.files)

    if args.skip:
        logging.warning('Skipping update trackers for project %s', args.project)
        remove_files(files, project)
    else:
        tracker = build_tracker(args, project)
        tracker.retrieve(files=files)

if __name__ == '__main__':
    main()
