"""
Script that accesses a file store to retrieve the dropins for a certain project.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
from configparser import RawConfigParser
import logging
import os
import shutil
from gatherer.files import OwnCloud_Store, PathExistenceError
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = RawConfigParser()
    config.read("settings.cfg")

    parser = argparse.ArgumentParser(description='Retrieve the dropin files')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--type', default=config.get('dropins', 'type'),
                        help='typoe of the data store (owncloud)')
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

    store_types = {
        'owncloud': OwnCloud_Store
    }

    args = parse_args()
    if args.type not in store_types:
        raise RuntimeError('Store type {} is not supported'.format(args.type))

    store_type = store_types[args.type]
    store = store_type(args.url)
    store.login(args.username, args.password)

    path = os.path.join('dropins', args.project)
    if os.path.exists(path):
        logging.info('Moving old path %s to a backup location', path)
        shutil.move(path, os.path.join('dropins', 'backup', args.project))

    try:
        store.get_directory(path, path)
    except PathExistenceError:
        logging.warning('Project %s has no dropin files', args.project)
    else:
        logging.info('Retrieved dropins for project %s', args.project)

if __name__ == "__main__":
    main()
