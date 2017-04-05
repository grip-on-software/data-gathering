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
import configparser
import os
import shutil
from zipfile import ZipFile
# Not-standard imports
import requests

def parse_args():
    """
    Parse command line arguments.
    """

    config = configparser.RawConfigParser()
    config.read("settings.cfg")

    parser = argparse.ArgumentParser(description='Retrieve the database importer')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--path', default=None,
                       help='local path to retrieve the dist directory from')
    group.add_argument('--url', default=config.get('importer', 'url'),
                       help='url to retrieve a dist.zip file from')
    group.add_argument('--base', default='.',
                       help='directory to place the importer and libraries in')

    args = parser.parse_args()
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
    shutil.move('dist/data_vcsdev_to_dev.json',
                os.path.join(args.base, 'data_vcsdev_to_dev.json'))
    shutil.move('dist/lib/', args.base)
    shutil.rmtree('dist')

if __name__ == "__main__":
    main()
