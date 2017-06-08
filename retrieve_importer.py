"""
Script for downloading the Java database importer from a URL and extracting it
such that the Jenkins scraper can run all programs.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import filecmp
import os
import shutil
import tempfile
from zipfile import ZipFile
# Not-standard imports
import requests
from gatherer.config import Configuration
from gatherer.files import File_Store
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Retrieve the database importer and auxiliary data'
    parser = argparse.ArgumentParser(description=description)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--path', default=None,
                       help='local path to retrieve the dist directory from')
    group.add_argument('--url', default=config.get('importer', 'url'),
                       help='url to retrieve a dist.zip file from')
    group.add_argument('--base', default='.',
                       help='directory to place the importer and libraries in')
    parser.add_argument('--type', default=config.get('dropins', 'type'),
                        help='type of the data store (owncloud)')
    parser.add_argument('--store', default=config.get('dropins', 'url'),
                        help='URL of the data store')
    parser.add_argument('--username', default=config.get('dropins', 'username'),
                        help='user to connect to the file store with')
    parser.add_argument('--password', default=config.get('dropins', 'password'),
                        help='password to connect to the file store with')
    parser.add_argument('--no-files', action='store_false', default=True,
                        dest='files', help='Skip retrieving files from store')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    if args.path is not None:
        shutil.copytree(os.path.join(os.path.expanduser(args.path), 'dist/'),
                        'dist/')
    else:
        request = requests.get(args.url, stream=True)
        with open('dist.zip', 'wb') as output_file:
            for chunk in request.iter_content(chunk_size=128):
                output_file.write(chunk)

        with ZipFile('dist.zip', 'r') as dist_zip:
            dist_zip.extractall()

        os.remove('dist.zip')

    # Check if 'dist' is the directory we want to place it in
    if os.path.realpath(args.base) == os.path.realpath('dist'):
        return

    if os.path.exists(os.path.join(args.base, 'lib')):
        shutil.rmtree(os.path.join(args.base, 'lib'))

    shutil.move('dist/importerjson.jar',
                os.path.join(args.base, 'importerjson.jar'))
    shutil.move('dist/lib/', args.base)
    shutil.rmtree('dist')

    if args.files:
        store_type = File_Store.get_type(args.type)
        store = store_type(args.store)
        store.login(args.username, args.password)

        path = tempfile.mktemp()
        data_file = 'data_vcsdev_to_dev.json'
        store.get_file('import/{}'.format(data_file), path)
        if not os.path.exists(data_file) or filecmp.cmp(data_file, path):
            shutil.move(path, data_file)
        else:
            raise RuntimeError('Not overwriting potentially updated file {}'.format(data_file))

if __name__ == "__main__":
    main()
