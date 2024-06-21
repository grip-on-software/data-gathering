"""
Script that accesses a file store to retrieve the dropins for a certain project.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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
import shutil
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.files import File_Store, PathExistenceError
from gatherer.log import Log_Setup

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Retrieve the dropin files')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--skip', action='store_true', default=False,
                        help='Do not retrieve dropins but remove local files')
    parser.add_argument('--type', default=config.get('dropins', 'type'),
                        help='type of the data store (owncloud)')
    parser.add_argument('--url', default=config.get('dropins', 'url'),
                        help='URL of the data store')
    parser.add_argument('--path', default='dropins',
                        help='Remote path prefix, without project directory')
    parser.add_argument('--username', default=config.get('dropins', 'username'),
                        help='user to connect to the file store with')
    parser.add_argument('--password', default=config.get('dropins', 'password'),
                        help='password to connect to the file store with')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    remote_path = f'{args.path}/{args.project}'
    if project.dropins_key.exists():
        logging.info('Removing old dropins path %s', project.dropins_key)
        shutil.rmtree(str(project.dropins_key))

    if args.skip:
        logging.warning('Skipped dropins import for project %s', args.project)
        return

    store_type = File_Store.get_type(args.type)
    store = store_type(args.url)
    store.login(args.username, args.password)

    try:
        store.get_directory(remote_path, str(project.dropins_key))
    except PathExistenceError:
        logging.warning('Project %s has no dropin files', args.project)
    else:
        logging.info('Retrieved dropins for project %s', args.project)

if __name__ == "__main__":
    main()
