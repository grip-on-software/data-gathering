"""
Script to checkout or update the repository that contains project definitions
with quality metrics.
"""

import argparse
import logging
import os
from gatherer.domain import Project
from gatherer.domain.source import Git
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    description = 'Obtain quality metrics definitions repository'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('project', help='project key')
    parser.add_argument('--repo', default=None,
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
    if args.repo is not None:
        repo_path = args.repo
    else:
        repo_path = project.get_key_setting('definitions', 'path')

    if isinstance(source, Git):
        repository = repo_class.from_source(source, repo_path)
    elif os.path.exists(repo_path):
        logging.info('Updating quality metrics repository %s', repo_path)
        repository = repo_class(source, repo_path)
        repository.update()
    else:
        logging.info('Checking out quality metrics repository to %s', repo_path)
        repository = repo_class.from_source(source, repo_path)
        repository.checkout()

if __name__ == '__main__':
    main()
