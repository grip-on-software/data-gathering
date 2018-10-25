"""
Script to import dumps of BigBoat health status information into a database.
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
from timeit import default_timer as timer

from gatherer.bigboat import Statuses
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Import BigBoat status dump into database'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('project', help='project key to import for')
    parser.add_argument('--path', default=None,
                        help='local path to the JSON file')
    parser.add_argument('--user', default=config.get('database', 'username'),
                        help='username to connect to the database with')
    parser.add_argument('--password', default=config.get('database', 'password'),
                        help='password to connect to the database with')
    parser.add_argument('--host', default=config.get('database', 'host'),
                        help='host name of the database to connect to')
    parser.add_argument('--database', default=config.get('database', 'name'),
                        help='database name to retrieve from')
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

    if args.path is None:
        status_filename = os.path.join(project.export_key, "data_status.json")
    else:
        status_filename = args.path

    start = timer()
    with Statuses(project, user=args.user, password=args.password,
                  host=args.host, database=args.database) as statuses:
        result = True
        with open(status_filename, 'r') as status_file:
            for line in status_file:
                result = statuses.add_batch(json.loads(line))
                if not result:
                    break

        result = statuses.update()
        if not result:
            logging.error('Could not import: database unavailable or project not known')

    end = timer()
    logging.info('Imported BigBoat status information in %d seconds', end - start)

if __name__ == '__main__':
    main()
