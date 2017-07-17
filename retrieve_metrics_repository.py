"""
Script to checkout or update the repository that contains project definitions
with quality metrics.
"""

import argparse
import logging
import os
import shutil
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
                        help='Directory to check out the repository to')
    parser.add_argument('--delete', action='store_true', default=False,
                        help='Delete local repository instead of retrieving it')
    parser.add_argument('--all', action='store_true', default=False,
                        help='Retrieve or delete all repositories, not a sparse subset')

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def delete_repository(source, repo_path, paths=None):
    """
    Delete a local version of a project definition metrics repository.
    """

    if paths is not None:
        # Remove repository from sparse checkout
        logging.info('Removing paths from sparse checkout of %s: %s',
                     repo_path, ', '.join(paths))
        repo_class = source.repository_class
        repository = repo_class(source, repo_path)
        repository.checkout_sparse(paths, remove=True)
        return
    elif os.path.exists(repo_path):
        logging.info('Deleting quality metrics repository %s', repo_path)
        shutil.rmtree(repo_path)
    else:
        logging.warning('Local quality metrics repository %s did not exist',
                        repo_path)

def retrieve_repository(source, repo_path, paths=None):
    """
    Retrieve a project definition metrics repository.
    """

    repo_class = source.repository_class
    if isinstance(source, Git):
        logging.info('Pulling quality metrics repository %s', repo_path)
        repository = repo_class.from_source(source, repo_path, checkout=paths)
    elif os.path.exists(repo_path):
        logging.info('Updating quality metrics repository %s', repo_path)
        repository = repo_class(source, repo_path)
        repository.checkout_sparse(paths)
    else:
        logging.info('Checking out quality metrics repository to %s', repo_path)
        repository = repo_class.from_source(source, repo_path)
        repository.checkout(paths=paths)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    if project.quality_metrics_name is None:
        logging.warning('Project %s has no quality metrics definitions',
                        project.key)
        return

    source = project.project_definitions_source
    default_repo_path = project.get_key_setting('definitions', 'path',
                                                project.quality_metrics_name)
    if args.repo is not None:
        repo_path = args.repo
    else:
        repo_path = default_repo_path

    required_paths = project.get_key_setting('definitions', 'required_paths')
    if required_paths:
        paths = required_paths.split(',')
    else:
        paths = []

    is_sparse_base = '/' not in default_repo_path.rstrip('/')
    if is_sparse_base:
        paths.append(project.quality_metrics_name)

        if not args.delete:
            git_directory = os.path.join(repo_path, '.git')
            if os.path.exists(repo_path) and not os.path.exists(git_directory):
                # The sparse clone has not yet been create (no .git directory)
                # but it must be placed in the root directory of the clones.
                # The other clones must be removed before the clone operation.
                logging.info('Making way to clone into %s', repo_path)
                delete_repository(source, repo_path)

    if args.all or not paths:
        paths = None

    base = project.get_key_setting('definitions', 'base')
    base_path = project.get_key_setting('definitions', 'path', base,
                                        project=False)
    base_source = project.make_project_definitions(base=True)

    if args.delete:
        delete_repository(source, repo_path, paths=paths)

        # Delete base code as well if requested (and not already deleted by the
        # sparse base checkout).
        if args.all and not is_sparse_base:
            delete_repository(base_source, base_path)

        return

    retrieve_repository(source, repo_path, paths=paths)
    retrieve_repository(base_source, base_path)

if __name__ == '__main__':
    main()
