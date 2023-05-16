"""
Module that handles access to and remote updates of a Git repository.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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

from datetime import datetime
from io import BytesIO
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, AbstractSet, Dict, Iterator, List, MutableSet, \
    Optional, Pattern, Sequence, Tuple, Union, TYPE_CHECKING
from git import Git, Repo, Blob, Commit, DiffIndex, TagReference, NULL_TREE, \
    InvalidGitRepositoryError, NoSuchPathError, GitCommandError
from ordered_set import OrderedSet
from .progress import Git_Progress
from ..table import Table, Key_Table
from ..utils import convert_local_datetime, format_date, parse_unicode, Iterator_Limiter
from ..version_control.repo import Change_Type, Version_Control_Repository, \
    RepositoryDataException, RepositorySourceException, FileNotFoundException, \
    PathLike, Version
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
else:
    Project = object
    Source = object

class Sparse_Checkout_Paths:
    """
    Reader and writer for the sparse checkout information file that tracks which
    paths should be checked out in a sparse checkout of the repository.

    """

    # Path within the git configuration directory.
    PATH = 'info'
    # File name of the information file.
    FILE = 'sparse-checkout'

    def __init__(self, repo: Repo) -> None:
        self._repo = repo
        self._path = Path(self._repo.git_dir, self.PATH, self.FILE)

    def get(self) -> MutableSet[str]:
        """
        Retrieve the current list of paths to check out from the sparse checkout
        information file.
        """

        if self._path.exists():
            with self._path.open('r', encoding='utf-8') as sparse_file:
                return OrderedSet(sparse_file.read().split('\n'))

        return OrderedSet()

    def _write(self, paths: AbstractSet[str]) -> None:
        with self._path.open('w', encoding='utf-8') as sparse_file:
            sparse_file.write('\n'.join(paths))

    def set(self, paths: Sequence[str], append: bool = True) -> None:
        """
        Accept paths in the local clone by updating the paths to check out in
        the sparse checkout information file.

        If `append` is `True`, the unique paths stored previosly in the file
        are kept, otherwise they are overwritten.
        """

        if append:
            original_paths = self.get()
        else:
            original_paths = OrderedSet()

        self._write(original_paths | set(paths))

    def remove(self, paths: Sequence[str]) -> None:
        """
        Remove paths to check out in the sparse checkout information file.
        """

        new_paths = self.get()
        if not new_paths:
            new_paths = OrderedSet(['/*'])

        for path in paths:
            if path in new_paths:
                new_paths.remove(path)
            else:
                new_paths.add(f'!{path}')

        self._write(new_paths)

class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    # How often to log Git clone/pull/fetch progress
    DEFAULT_UPDATE_RATIO = 10
    # Number of commits to obtain from git in one iteration
    BATCH_SIZE = 10000
    # Maximum number of commits to obtain
    MAX_SIZE = 100000
    # How often to log the number of commits that have been analyzed
    LOG_SIZE = 1000

    MERGE_PATTERNS: Sequence[Pattern[str]] = \
        tuple(re.compile(pattern) for pattern in (
            r".*\bMerge branch '([^']+)'",
            r".*\bMerge remote-tracking branch '(?:(?:refs/)?remotes)?origin/([^']+)'",
            r"Merge pull request \d+ from ([^\s]+) into .+",
            r"([A-Z]{3,}\d+) [Mm]erge",
            r"(?:Merge )?([^\s]+) >\s?master"
        ))

    AUXILIARY_TABLES = {'change_path', 'tag'}

    def __init__(self, source: Source, repo_directory: PathLike,
                 progress: Optional[Union[bool, int]] = None, **kwargs: Any) -> None:
        super().__init__(source, repo_directory, **kwargs)
        self._repo: Optional[Repo] = None
        self._from_date = source.get_option('from_date')
        self._tag = source.get_option('tag')
        self._prev_head = NULL_TREE

        # If `progress` is `True`, then add progress lines from Git commands to
        # the logging output. If `progress` is a nonzero number, then sample
        # from this number of lines. If it is not `False`, then use it as
        # a progress callback function.
        self._progress: Optional[Git_Progress] = None
        if progress is True:
            self._progress = Git_Progress(update_ratio=self.DEFAULT_UPDATE_RATIO)
        elif isinstance(progress, int) and progress > 0:
            self._progress = Git_Progress(update_ratio=progress)

        self._reset_limiter()
        self._tables.update({
            'change_path': Table('change_path'),
            'tag': Key_Table('tag', 'tag_name',
                             encrypt_fields=('tagger', 'tagger_email'))
        })

    def _reset_limiter(self) -> None:
        self._iterator_limiter = Iterator_Limiter(size=self.BATCH_SIZE,
                                                  maximum=self.MAX_SIZE)

    def _get_refspec(self, from_revision: Optional[Version] = None,
                     to_revision: Optional[Version] = None) -> str:
        # Determine special revision ranges from credentials settings.
        # By default, we retrieve all revisions from the default branch, but if
        # the tag defined in the credentials section exists, then we use this
        # tag as end point instead. Otherwise, the range can be limited by
        # a starting date defined in the credentials for compatibility with
        # partial migrations.
        default_to_revision = self.repo.head.commit.hexsha
        if self._tag is not None and self._tag in self.repo.tags:
            default_to_revision = self._tag
        elif from_revision is None and self._from_date is not None:
            from_revision = ''.join(('@', '{', self._from_date, '}'))

        # Format the range as a specifier that git rev-parse can handle.
        if from_revision is not None:
            if to_revision is not None:
                return f'{from_revision}...{to_revision}'

            return f'{from_revision}...{default_to_revision}'

        if to_revision is not None:
            return str(to_revision)

        return default_to_revision

    @classmethod
    def from_source(cls, source: Source, repo_directory: PathLike,
                    **kwargs: Any) -> 'Git_Repository':
        """
        Initialize a Git repository from its `Source` domain object.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.

        The keyword arguments may optionally include `checkout`. If this is
        not given or it is set to `False`, then the local directory does not
        contain the actual paths and files from the repository, similar to
        a bare checkout (except that the tree can be made intact again).
        A value of `True` checks out the entire repository as on a normal clone
        or pull. If `checkout` receives a list, then the paths in this list
        are added to a sparse checkout, and updated from the remote.

        Another optional keyword argument is `shallow`. If it is set to `True`,
        then the local directory only contains the default branch's head commit
        after cloning. Note that no precautions are made to prevent pulling in
        more commits unless `shallow` is provided to each such action.

        If `branch` is provided, then the repository is checked out to this
        branch's head after updating it.

        Use 'shared' to enable shared repository permissions during the clone
        and subsequent pulls. 'shared' may be a boolean to enable or disable
        global sharing, but it can also be a string such as "group" to enable
        a specific shared permission scheme. An existing repository clone with
        a different value for "core.sharedRepository" or "core.sharedrepository"
        cause a `RuntimeError`, and so does a combination of `shared` and
        `checkout` when the latter is a list of paths.

        If `force` is enabled, when a pull into an existing repository fails,
        then the local repository is deleted and a clone is attempted.
        This method raises a `RepositorySourceException` if a clone fails, or
        if a pull fails and `force` is not enabled.

        If `pull` is disabled, then no pull for an existing repository is
        attempted at all and `force` has no effect.
        """

        checkout = kwargs.pop('checkout', False)
        shallow = kwargs.pop('shallow', False)
        branch = kwargs.pop('branch', None)
        shared = kwargs.pop('shared', False)
        force = kwargs.pop('force', False)
        pull = kwargs.pop('pull', False)

        repository = cls(source, repo_directory, **kwargs)
        if repository.repo_directory.exists():
            if not pull:
                return repository

            try:
                repository.pull(shallow=shallow, shared=shared,
                                checkout=checkout, branch=branch, force=force)
                return repository
            except RepositorySourceException:
                if not force:
                    raise

        if isinstance(checkout, bool):
            repository.clone(checkout=checkout, shallow=shallow,
                             branch=branch, shared=shared)
        elif shared is not False:
            # Checkout is a list of paths to checkout, so sparse
            raise RuntimeError('Shared repositories are not supported for sparse checkouts')
        else:
            repository.checkout(paths=checkout, shallow=shallow, branch=branch)

        return repository

    def _cleanup(self) -> None:
        logging.warning('Deleting clone to make way in %s', self.repo_directory)
        try:
            shutil.rmtree(str(self.repo_directory))
        except OSError as error:
            raise RepositorySourceException('Could not delete clone directory') from error

    def pull(self, shallow: bool = False, shared: bool = False,
             checkout: Union[bool, Sequence[str]] = True,
             branch: Optional[str] = None, force: bool = False) -> None:
        """
        Pull the latest changes into the existing local repository.

        If `shallow` is set to `True`, then the local repository will only
        pull in the default branch's head commit. If `shared` is given, then
        the repository's permissions are set to global or group permissions.
        `checkout` may be set to `False` to disable a local repository checkout
        of the latest commits, or to a list of paths to check out. If `branch`
        is provided, then the repository is checked out to the head of this
        branch after updating it. If `force` is enabled, then an attempt is
        made to clean up when the first attempt fails rather than raising
        an exception.
        """

        try:
            if not self.is_shared(shared=shared):
                raise RepositorySourceException(f"Clone was not shared as '{shared}'")

            if self.is_empty():
                return

            if isinstance(checkout, bool):
                self.update(shallow=shallow, checkout=checkout, branch=branch)
            else:
                self.checkout_sparse(checkout, shallow=shallow, branch=branch)
        except RepositorySourceException as error:
            if not force:
                raise error

            logging.exception('Could not pull into existing repository %s',
                              self.repo_directory)
            try:
                self._cleanup()
            except RepositorySourceException as cleanup_error:
                raise cleanup_error from error

    @classmethod
    def is_up_to_date(cls, source: Source, latest_version: Version,
                      update_tracker: Optional[str] = None,
                      branch: Optional[str] = None) -> bool:
        if branch is None:
            branch = 'master'

        git = Git()
        git.update_environment(**cls._create_environment(source, git))
        # Check if the provided version is up to date compared to master.
        try:
            remote_refs = git.ls_remote('--heads', source.url, branch)
        except GitCommandError as error:
            raise RepositorySourceException('Could not check up-to-dateness') from error

        head_version = remote_refs.split('\t', 1)[0]
        if head_version == str(latest_version):
            return True

        return False

    @classmethod
    def get_branches(cls, source: Source) -> List[str]:
        git = Git()
        git.update_environment(**cls._create_environment(source, git))
        try:
            remote_refs = git.ls_remote('--heads', source.url)
        except GitCommandError as error:
            raise RepositorySourceException('Could not check branches') from error

        prefix = 'refs/heads/'
        return [
            ref.split('\t', 1)[1][len(prefix):]
            for ref in remote_refs.split('\n')
        ]

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            try:
                # Use property setter so that the environment credentials path
                # is also updated.
                repo = Repo(str(self._repo_directory))
                self._update_environment(repo)
                self._repo = repo
            except (InvalidGitRepositoryError, NoSuchPathError) as error:
                raise RepositorySourceException('Invalid or nonexistent path') from error

        return self._repo

    @repo.setter
    def repo(self, repo: object) -> None:
        if not isinstance(repo, Repo):
            raise TypeError('Repository must be a gitpython Repo instance')

        self._update_environment(repo)
        self._repo = repo

    def _update_environment(self, repo: Repo) -> None:
        environment = self._create_environment(self.source, repo.git)
        repo.git.update_environment(**environment)

    @classmethod
    def _get_ssh_command(cls, source: Source) -> str:
        if source.credentials_path is None:
            raise ValueError('Must have a credentials path')

        logging.debug('Using credentials path %s', source.credentials_path)
        ssh_command = f"ssh -i '{source.credentials_path}'"
        if source.get_option('unsafe_hosts'):
            ssh_command = (
                f'{ssh_command} -o StrictHostKeyChecking=no'
                f'-o UserKnownHostsFile={os.devnull}'
            )

        return ssh_command

    @classmethod
    def _create_environment(cls, source: Source, git: Optional[Git] = None) -> Dict[str, str]:
        """
        Retrieve the environment variables for the Git subcommands.
        """

        environment: Dict[str, str] = {}

        if source.credentials_path is not None:
            ssh_command = cls._get_ssh_command(source)

            if git is None:
                git = Git()

            version_info = git.version_info
            if version_info < (2, 3, 0):
                with tempfile.NamedTemporaryFile(delete=False,
                                                 encoding='utf-8') as tmpfile:
                    tmpfile.write(f'{ssh_command} $*'.encode('utf-8'))
                    command_filename = tmpfile.name

                Path(command_filename).chmod(0o700)
                environment['GIT_SSH'] = command_filename
                logging.debug('Command filename: %s', command_filename)
            else:
                environment['GIT_SSH_COMMAND'] = ssh_command

        return environment

    @property
    def version_info(self) -> Tuple[int, ...]:
        return self.repo.git.version_info

    @property
    def default_branch(self) -> str:
        """
        Retrieve the working branch from which to collect data and to update.

        By default, this is the currently checked-out branch.
        """

        return self.repo.head.ref.name

    @property
    def prev_head(self) -> Commit:
        """
        Indicator of the previous head state before a pull, fetch/merge, or
        checkout operation, such as when pulling an existing repository.
        The previous head is then given by the commit that the branch was on
        in before the latest relevant operation.

        If no such operation has been done (or the repository was just cloned),
        then this property returns the NULL_TREE object, which indicates the
        empty tree (no commit has been made). The return value is thus suitable
        to use in GitPython difference operations.
        """

        return self._prev_head

    def is_empty(self) -> bool:
        try:
            return not self.repo.branches
        except RepositorySourceException:
            return True

    def is_shared(self, shared: bool = True) -> bool:
        """
        Check whether the repository is shared in the same way as the `shared`
        parameter indicates. A `shared` value of `True` may correspond to
        either "group" or "true" in the repository configuration, while when
        `shared` is `False`, the configuration must be set to "umask", "false"
        or be unset in order to match. The `shared` value may also be "all"
        which matches "all", "world" or "everybody" configuration. For future
        compatibility, other `shared` may match exactly with the configuration.

        Note that this only matches configuration variables written as either
        "sharedRepository" or "sharedrepository" in the "core" section of the
        Git config; other case variants are not looked up.
        """

        shared_mapping = {
            "true": True,
            "group": True,
            "false": False,
            "umask": False,
            "all": "all",
            "world": "all",
            "everybody": "all"
        }

        config = self.repo.config_reader()
        value = config.get_value('core', 'sharedRepository', default=False)
        if value is False:
            value = config.get_value('core', 'sharedrepository', default=False)
        if not isinstance(value, str) or value not in shared_mapping:
            return shared == value

        return shared == shared_mapping[value]

    def update(self, shallow: bool = False, checkout: bool = True,
               branch: Optional[str] = None) -> None:
        # Update the repository from the origin URL.
        try:
            if branch is None:
                branch = self.default_branch

            if not self.repo.remotes:
                raise RepositorySourceException('No remotes defined for repository')

            refspec = f'origin/{branch}'
            self._prev_head = self.repo.head.commit
            if shallow:
                self.repo.remotes.origin.fetch(branch, depth=1,
                                               progress=self._progress)
                if checkout:
                    self.repo.head.reset(refspec, hard=True)

                self.repo.git.reflog(['expire', '--expire=now', '--all'])
                self.repo.git.gc(['--prune=now'])
            elif checkout and branch != self.default_branch:
                self.repo.remotes.origin.fetch(branch, progress=self._progress)
                self.repo.git.checkout(branch)
                self.repo.head.reset(refspec, hard=True)
            elif checkout:
                self.repo.remotes.origin.pull(branch, progress=self._progress)
            else:
                # Update local branch but not the working tree
                spec = f'{branch}:{branch}'
                self.repo.remotes.origin.fetch(spec,
                                               update_head_ok=True,
                                               progress=self._progress)
        except GitCommandError as error:
            raise RepositorySourceException('Could not update clone') from error

    def checkout(self, paths: Optional[Sequence[str]] = None,
                 shallow: bool = False, branch: Optional[str] = None) -> None:
        self.clone(checkout=paths is None, shallow=shallow, branch=branch)

        if paths is not None:
            self.checkout_sparse(paths, shallow=shallow, branch=branch)

    def _checkout_index(self) -> None:
        try:
            self.repo.git.read_tree(['-m', '-u', 'HEAD'])
        except GitCommandError as error:
            raise RepositorySourceException('Could not checkout index') from error

    def checkout_sparse(self, paths: Sequence[str], remove: bool = False,
                        shallow: bool = False, branch: Optional[str] = None) -> None:
        self.repo.config_writer().set_value('core', 'sparseCheckout', True)
        sparse = Sparse_Checkout_Paths(self.repo)

        if remove:
            sparse.remove(paths)
        else:
            sparse.set(paths)

        # Now checkout the sparse directories into the index.
        self._checkout_index()

        # Ensure repository is up to date.
        self.update(shallow=shallow, branch=branch)

    def clone(self, checkout: bool = True, shallow: bool = False,
              shared: bool = False, branch: Optional[str] = None) -> None:
        """
        Clone the repository, optionally according to a certain checkout
        scheme. If `checkout` is `False`, then do not check out the local files
        of the default branch (all repository actions still function).

        If `shallow` is `True`, then only the default branch's head commit is
        fetched. Note that not precautions are made to prevent pulling in more
        commits later on unless `shallow` is used for all actions.

        If `shared` is something other than `False`, then this value is used
        for the core.sharedRepository configuration, causing the repository
        permissions to be set such that it is shared with a group or all.
        A boolean `True` becomes "true" which means group sharing. Note that
        this option does not alter any ownership behavior, is dependent on
        the user performing actions and the setgid permission on the (parent)
        directory that may alter the group used.

        If the repository cannot be updated due to a source issue, then this
        method may raise a `RepositorySourceException`.
        """

        kwargs: Dict[str, Union[bool, int, str]] = {
            "no_checkout": not checkout
        }
        if shallow:
            kwargs["depth"] = 1
        if shared is not False:
            value = "true" if shared is True else shared
            kwargs["config"] = f"core.sharedRepository={value}"
        if branch is not None:
            kwargs["branch"] = branch

        try:
            environment = self._create_environment(self.source)
            self.repo = Repo.clone_from(self.source.url,
                                        str(self.repo_directory),
                                        progress=self._progress,
                                        env=environment,
                                        **kwargs)
        except GitCommandError as error:
            raise RepositorySourceException('Could not clone repository') from error

    def _query(self, refspec: str, paths: Union[str, Sequence[str]] = '',
               descending: bool = True) -> Iterator[Commit]:
        try:
            return self.repo.iter_commits(refspec, paths=paths,
                                          max_count=self._iterator_limiter.size,
                                          skip=self._iterator_limiter.skip,
                                          reverse=not descending)
        except GitCommandError as error:
            raise RepositoryDataException('Could not search commits') from error

    def find_commit(self, committed_date: datetime) -> Optional[str]:
        """
        Find a commit SHA by its committed date, assuming the date is unique.

        If the commit could not be found, then `None` is returned.
        """

        date_epoch = committed_date.strftime('%s')
        rev_list_args = {
            'max_count': 1,
            'min_age': date_epoch,
            'max_age': date_epoch
        }
        rev = self.default_branch
        try:
            commit: Commit = next(self.repo.iter_commits(rev=rev, paths='',
                                                         **rev_list_args))
            return commit.hexsha
        except StopIteration:
            return None
        except GitCommandError as error:
            raise RepositoryDataException('Could not retrieve commit') from error

    def get_versions(self, filename: str = '',
                     from_revision: Optional[Version] = None,
                     to_revision: Optional[Version] = None,
                     descending: bool = False, **kwargs: Any) -> List[Dict[str, str]]:
        refspec = self._get_refspec(from_revision, to_revision)
        return self._parse(refspec, paths=filename, descending=descending, **kwargs)

    def get_data(self, from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None,
                 force: bool = False, **kwargs: Any) -> List[Dict[str, str]]:
        versions = super().get_data(from_revision, to_revision, force=force,
                                    **kwargs)

        self._parse_tags()

        return versions

    def _parse(self, refspec: str, paths: Union[str, List[str]] = '',
               descending: bool = True, **kwargs: Any) -> List[Dict[str, str]]:
        self._reset_limiter()

        version_data: List[Dict[str, str]] = []
        commits = self._query(refspec, paths=paths, descending=descending)
        had_commits = True
        count = 0
        while self._iterator_limiter.check(had_commits):
            had_commits = False

            try:
                for commit in commits:
                    had_commits = True
                    count += 1
                    version_data.append(self._parse_version(commit, **kwargs))

                    if count % self.LOG_SIZE == 0:
                        logging.info('Analysed commits up to %d', count)
            except GitCommandError as error:
                raise RepositoryDataException('Could not analyze commit') from error

            logging.info('Analysed batch of commits, now at %d', count)

            self._iterator_limiter.update()

            if self._iterator_limiter.check(had_commits):
                commits = self._query(refspec, paths=paths, descending=descending)

        return version_data

    def _parse_version(self, commit: Commit, stats: bool = True,
                       **kwargs: Any) -> Dict[str, str]:
        """
        Convert one commit instance to a dictionary of properties.
        """

        commit_datetime = convert_local_datetime(commit.committed_datetime)
        author_datetime = convert_local_datetime(commit.authored_datetime)

        commit_type = str(commit.type)
        if len(commit.parents) > 1:
            commit_type = 'merge'

        developer = parse_unicode(commit.author.name)
        git_commit = {
            # Primary data
            'repo_name': str(self._repo_name),
            'version_id': str(commit.hexsha),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(commit.message),
            'type': commit_type,
            'developer': developer,
            'developer_username': developer,
            'developer_email': str(commit.author.email),
            'commit_date': format_date(commit_datetime),
            'author_date': format_date(author_datetime)
        }

        if stats:
            git_commit.update(self._get_diff_stats(commit))
            git_commit['branch'] = self._get_original_branch(commit)
            self._parse_change_stats(commit)

        return git_commit

    @staticmethod
    def _get_diff_stats(commit: Commit) -> Dict[str, str]:
        cstotal = commit.stats.total

        return {
            # Statistics
            'insertions': str(cstotal['insertions']),
            'deletions': str(cstotal['deletions']),
            'number_of_files': str(cstotal['files']),
            'number_of_lines': str(cstotal['lines']),
            'size': str(commit.size)
        }

    def _get_original_branch(self, commit: Commit) -> str:
        try:
            commits = self.repo.iter_commits(f'{commit.hexsha}..HEAD',
                                             ancestry_path=True, merges=True,
                                             reverse=True)
        except GitCommandError:
            logging.exception('Cannot find original branch for %s in repo %s',
                              commit.hexsha, self.repo_name)
            return str(0)

        try:
            merge_commit: Commit = next(commits)
        except StopIteration:
            return str(0)

        merge_message = parse_unicode(merge_commit.message)
        for pattern in self.MERGE_PATTERNS:
            match = pattern.match(merge_message)
            if match:
                return match.group(1)

        return str(0)

    @staticmethod
    def _format_replaced_path(old_path: str, new_path: str) -> str:
        # Algorithm comparable to pprint_rename function as implemented in git
        # to format a path with partial replacement (move). See git's diff.c.
        # Not implemented: C-style quoted files with non-unicode characters.

        # Find common prefix
        prefix_length = 0
        for index, pair in enumerate(zip(old_path, new_path)):
            if pair[0] != pair[1]:
                break
            if pair[0] == '/':
                prefix_length = index + 1

        # Find common suffix
        suffix_length = 0
        prefix_adjust_for_slash = 1 if prefix_length else 0
        old_index = len(old_path) - 1
        new_index = len(new_path) - 1
        while prefix_length - prefix_adjust_for_slash <= old_index and \
                prefix_length - prefix_adjust_for_slash <= new_index and \
                old_path[old_index] == new_path[new_index]:
            if old_path[old_index] == '/':
                suffix_length = len(old_path) - old_index

            old_index -= 1
            new_index -= 1

        # Format replaced path
        old_midlen = max(0, len(old_path) - suffix_length)
        new_midlen = max(0, len(new_path) - suffix_length)

        mid_name = (
            f'{old_path[prefix_length:old_midlen]} => '
            f'{new_path[prefix_length:new_midlen]}'
        )
        if prefix_length + suffix_length > 0:
            return (
                f'{old_path[:prefix_length]}{{{mid_name}}}'
                f'{old_path[len(old_path)-suffix_length:]}'
            )

        return mid_name

    def _parse_change_stats(self, commit: Commit) -> None:
        if commit.parents:
            parent_diffs: Sequence[DiffIndex] = \
                tuple(commit.diff(parent, R=True) for parent in commit.parents)
        else:
            parent_diffs = (commit.diff(NULL_TREE),)

        for diffs in parent_diffs:
            self._parse_change_diffs(commit, diffs)

    def _parse_change_diffs(self, commit: Commit, diffs: DiffIndex) -> None:
        files = commit.stats.files
        for diff in diffs:
            old_file = diff.a_path
            new_file = diff.b_path
            if old_file is None or new_file is None:
                continue

            change_type = Change_Type.from_label(diff.change_type)
            if old_file != new_file:
                stat_file = self._format_replaced_path(old_file, new_file)
            else:
                stat_file = old_file

            if stat_file not in files:
                logging.debug('File change %s in commit %s has no stats',
                              stat_file, commit.hexsha)
                continue

            insertions = files[stat_file]['insertions']
            deletions = files[stat_file]['deletions']

            if diff.b_blob is None:
                size = 0
            else:
                try:
                    size = diff.b_blob.size
                except ValueError:
                    # Missing blob or parent commit
                    logging.info('File change %s in commit %s has no parent',
                                 stat_file, commit.hexsha)
                    continue

            change_data = {
                'repo_name': str(self._repo_name),
                'version_id': str(commit.hexsha),
                'file': str(new_file),
                'change_type': str(change_type.value),
                'insertions': str(insertions),
                'deletions': str(deletions),
                'size': str(size)
            }
            self._tables['change_path'].append(change_data)

    def _parse_tags(self) -> None:
        for tag_ref in self.repo.tags:
            self._parse_tag(tag_ref)

    def _parse_tag(self, tag_ref: TagReference) -> None:
        tag_data = {
            'repo_name': str(self._repo_name),
            'tag_name': tag_ref.name,
            'version_id': str(tag_ref.commit.hexsha),
            'message': str(0),
            'tagged_date': str(0),
            'tagger': str(0),
            'tagger_email': str(0)
        }

        if tag_ref.tag is not None:
            tag_data['message'] = parse_unicode(tag_ref.tag.message)

            tag_timestamp = tag_ref.tag.tagged_date
            tagged_datetime = datetime.fromtimestamp(tag_timestamp)
            tag_data['tagged_date'] = format_date(tagged_datetime)

            tag_data['tagger'] = parse_unicode(tag_ref.tag.tagger.name)
            tag_data['tagger_email'] = str(tag_ref.tag.tagger.email)

        self._tables['tag'].append(tag_data)

    def get_latest_version(self) -> Version:
        try:
            return self.repo.rev_parse(self.default_branch).hexsha
        except GitCommandError as error:
            raise RepositoryDataException('Could not retrieve latest version') from error

    def get_contents(self, filename: str,
                     revision: Optional[Version] = None) -> bytes:
        try:
            if revision is not None:
                commit = self.repo.commit(str(revision))
            else:
                commit = self.repo.commit('HEAD')
        except GitCommandError as error:
            raise RepositoryDataException('Could not retrieve commit') from error

        try:
            blob = commit.tree.join(filename)
        except KeyError as error:
            raise FileNotFoundException('Could not retrieve file') from error

        if not isinstance(blob, Blob):
            raise FileNotFoundException(f'Path {filename} has no Blob object')

        stream = BytesIO()
        blob.stream_data(stream)
        return stream.getvalue()
