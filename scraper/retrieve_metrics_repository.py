"""
Script to checkout or update the repository that contains project definitions
with quality metrics.
"""

from argparse import ArgumentParser, Namespace
import logging
from pathlib import Path
import shutil
from typing import List, Optional, Tuple
from gatherer.domain import Project, Source
from gatherer.git.repo import Git_Repository
from gatherer.log import Log_Setup

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = 'Obtain quality metrics definitions repository'
    parser = ArgumentParser(description=description)
    parser.add_argument('project', help='project key')
    parser.add_argument('--repo', default=None,
                        help='Directory to check out the repository to')
    parser.add_argument('--delete', action='store_true', default=False,
                        help='Delete local repository instead of retrieving it')
    parser.add_argument('--all', action='store_true', default=False,
                        help='Retrieve or delete all repositories, not a sparse subset')
    parser.add_argument('--force', action='store_true', default=False,
                        help='Delete and clone repository if pull fails')

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def delete_repository(source: Source, repo_path: Path,
                      paths: Optional[List[str]] = None) -> None:
    """
    Delete a local version of a project definition metrics repository.
    """

    repo_class = source.repository_class
    if repo_class is not None and paths is not None:
        # Remove repository from sparse checkout
        logging.info('Removing paths from sparse checkout of %s: %s',
                     repo_path, ', '.join(paths))
        repository = repo_class(source, repo_path)
        repository.checkout_sparse(paths, remove=True)
    elif repo_path.exists():
        logging.info('Deleting quality metrics repository %s', repo_path)
        shutil.rmtree(str(repo_path))
    else:
        logging.warning('Local quality metrics repository %s did not exist',
                        repo_path)

def retrieve_repository(source: Source, repo_path: Path,
                        paths: Optional[List[str]] = None,
                        force: bool = False) -> None:
    """
    Retrieve a project definition metrics repository from the `source` and
    make it available in `repo_path`. If `paths` is not `None`, then a subset
    of paths are checked out into the working tree.
    """

    repo_class = source.repository_class
    if repo_class is None:
        raise RuntimeError('Quality metrics repository has no version control')

    if issubclass(repo_class, Git_Repository):
        logging.info('Pulling quality metrics repository %s', repo_path)
        repo_class.from_source(source, repo_path,
                               pull=True,
                               checkout=paths if paths is not None else True,
                               force=force)
    elif repo_path.exists():
        logging.info('Updating quality metrics repository %s', repo_path)
        repository = repo_class(source, repo_path)
        if paths is None:
            repository.update()
        else:
            repository.checkout_sparse(paths)
    else:
        logging.info('Checking out quality metrics repository to %s', repo_path)
        repository = repo_class.from_source(source, repo_path)
        repository.checkout(paths=paths)

def cleanup_repository(source: Source, repo_path: Path) -> None:
    """
    Make sure that the repository path is clean such that we can pull or clone
    in it.
    """

    git_path = repo_path / '.git'
    if repo_path.exists() and not git_path.exists():
        # The sparse clone has not yet been created (no .git directory)
        # but it must be placed in the root directory of the clones.
        # The other clones must be removed before the clone operation.
        logging.info('Making way to clone into %s', repo_path)
        delete_repository(source, repo_path)

def check_paths(project: Project) -> Tuple[List[str], bool]:
    """
    Check which paths should be checked out for the repository if specified.
    """

    paths: List[str] = []
    if project.quality_metrics_name is None:
        return paths, False

    default_repo_path = project.get_key_setting('definitions', 'path',
                                                project.quality_metrics_name)
    required_paths = project.get_key_setting('definitions', 'required_paths')

    if required_paths:
        paths = required_paths.split(',')

    is_sparse_base = '/' not in default_repo_path.rstrip('/')
    if is_sparse_base:
        paths.append(project.quality_metrics_name)

    return paths, is_sparse_base

def perform(project: Project, source: Source, repo_path: Path,
            args: Namespace) -> None:
    """
    Perform updates to the metrics repository, such as pull and cleanup.
    """

    all_paths, is_sparse_base = check_paths(project)
    if is_sparse_base and not args.delete:
        # In order to retrieve the Git repository, we need to check if
        # we can actually clone/pull in the directory
        cleanup_repository(source, repo_path)

    paths: Optional[List[str]] = all_paths
    if args.all or not paths:
        paths = None

    base = project.get_key_setting('definitions', 'base')
    base_path = Path(project.get_key_setting('definitions', 'path', base,
                                             project=False))
    base_source = project.make_project_definitions(base=True)

    if args.delete:
        delete_repository(source, repo_path, paths=paths)

        # Delete base code as well if requested (and not already deleted by the
        # sparse base checkout).
        if args.all and not is_sparse_base:
            delete_repository(base_source, base_path)

        return

    retrieve_repository(source, repo_path, paths=paths, force=args.force)
    retrieve_repository(base_source, base_path, force=args.force)

def main() -> None:
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
    if source is None:
        logging.warning('Project %s has no definitions source', project.key)
        return

    default_repo_path = project.get_key_setting('definitions', 'path',
                                                project.quality_metrics_name)
    if args.repo is not None:
        repo_path = Path(args.repo)
    else:
        repo_path = Path(default_repo_path)

    perform(project, source, repo_path, args)

if __name__ == '__main__':
    main()
