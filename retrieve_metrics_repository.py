"""
Script to checkout or update the repository that contains project definitions
with quality metrics.
"""

import argparse
import logging
import os
from gatherer.config import Configuration
from gatherer.domain.project import Project_Meta
from gatherer.log import Log_Setup
from gatherer.svn import Subversion_Repository

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain quality metrics definitions repository'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--repo', default=config.get('definitions', 'path'),
                        help='directory to check out the repository to')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    meta = Project_Meta()
    source = meta.project_definitions_source
    if os.path.exists(args.repo):
        logging.info('Updating quality metrics repository %s', args.repo)
        repository = Subversion_Repository(source, args.repo)
        repository.update()
    else:
        logging.info('Checking out quality metrics repository to %s', args.repo)
        repository = Subversion_Repository.from_source(source, args.repo)
        repository.checkout()

if __name__ == '__main__':
    main()
