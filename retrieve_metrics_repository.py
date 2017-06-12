"""
Script to checkout or update the repository that contains project definitions
with quality metrics.
"""

import argparse
import logging
import os
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import Git
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain quality metrics definitions repository'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('project', help='project key')
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
    project = Project(args.project)
    source = project.project_definitions_source
    repo_class = source.repository_class
    if isinstance(source, Git):
        repository = repo_class.from_source(source, args.repo)
    elif os.path.exists(args.repo):
        logging.info('Updating quality metrics repository %s', args.repo)
        repository = repo_class(source, args.repo)
        repository.update()
    else:
        logging.info('Checking out quality metrics repository to %s', args.repo)
        repository = repo_class.from_source(source, args.repo)
        repository.checkout()

if __name__ == '__main__':
    main()
