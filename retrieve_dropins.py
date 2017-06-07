"""
Script that accesses a file store to retrieve the dropins for a certain project.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import logging
import os
import shutil
from gatherer.config import Configuration
from gatherer.files import File_Store, PathExistenceError
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Retrieve the dropin files')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--skip', action='store_true', default=False,
                        help='Do not retrieve dropins but remove local files')
    parser.add_argument('--type', default=config.get('dropins', 'type'),
                        help='type of the data store (owncloud)')
    parser.add_argument('--url', default=config.get('dropins', 'url'),
                        help='URL of the data store')
    parser.add_argument('--username', default=config.get('dropins', 'username'),
                        help='user to connect to the file store with')
    parser.add_argument('--password', default=config.get('dropins', 'password'),
                        help='password to connect to the file store with')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()

    path = os.path.join('dropins', args.project)
    if os.path.exists(path):
        logging.info('Removing old dropins path %s', path)
        shutil.rmtree(path)

    if args.skip:
        logging.warning('Skipped dropins import for project %s', args.project)
        return

    store_type = File_Store.get_type(args.type)
    store = store_type(args.url)
    store.login(args.username, args.password)

    try:
        store.get_directory(path, path)
    except PathExistenceError:
        logging.warning('Project %s has no dropin files', args.project)
    else:
        logging.info('Retrieved dropins for project %s', args.project)

if __name__ == "__main__":
    main()
