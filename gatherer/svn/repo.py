"""
Module that handles access to and remote updates of a Subversion repository.

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
import logging
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Sequence, \
    Tuple, Union, TYPE_CHECKING
# Non-standard imports
import dateutil.tz
import svn.common
import svn.exception
import svn.local
import svn.remote

from .difference import Difference
from ..table import Table, Key_Table
from ..utils import format_date, parse_unicode, Iterator_Limiter
from ..version_control.repo import Version_Control_Repository, \
    RepositoryDataException, RepositorySourceException, FileNotFoundException, \
    PathLike, Version
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Source
else:
    Source = object

LogEntry = NamedTuple('LogEntry', [('date', datetime),
                                   ('msg', str),
                                   ('revision', int),
                                   ('author', str),
                                   ('changelist', List[Tuple[str, str]])])

class UnsafeRemoteClient(svn.remote.RemoteClient):
    """
    A remote subversion client which trusts a server certificate, even
    if it has other verification failures than a self-signed certificate.
    """

    def run_command(self, subcommand: str, args: List[str], **kwargs: Any) \
            -> Union[bytes, List[str]]:
        failures = 'unknown-ca,cn-mismatch,expired,not-yet-valid,other'
        args.append(f'--trust-server-cert-failures={failures}')
        return super().run_command(subcommand, args, **kwargs)

class Subversion_Repository(Version_Control_Repository):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    AUXILIARY_TABLES = {'change_path', 'tag'}
    # Number of commits to obtain from git in one iteration
    BATCH_SIZE = 1000
    # Maximum number of commits to obtain
    MAX_SIZE = 10000

    def __init__(self, source: Source, repo_directory: PathLike, **kwargs: Any):
        super().__init__(source, repo_directory, **kwargs)
        self._repo: Optional[svn.common.CommonClient] = None
        self._version_info: Optional[Tuple[int, ...]] = None
        self._reset_limiter()
        self._tables.update({
            'change_path': Table('change_path'),
            'tag': Key_Table('tag', 'tag_name',
                             encrypt_fields=('tagger', 'tagger_email'))
        })

    def _reset_limiter(self) -> None:
        self._iterator_limiter = Iterator_Limiter(size=self.BATCH_SIZE,
                                                  maximum=self.MAX_SIZE)

    @classmethod
    def _create_environment(cls, source: Source) \
            -> Dict[str, Optional[Union[bool, str]]]:
        env: Dict[str, Optional[Union[bool, str]]] = {}
        if source.get_option('unsafe_hosts'):
            env['trust_cert'] = True
            env['username'] = source.get_option('username')
            env['password'] = source.get_option('password')

        return env

    @classmethod
    def _create_remote_repo(cls, source: Source) -> svn.remote.RemoteClient:
        env = cls._create_environment(source)
        if source.get_option('unsafe_hosts'):
            # Do not pass username and password as authority part of an URL to
            # an unsafe HTTPS host because it is also most likely misconfigured
            # in handling the authorization. Instead use the username and
            # password from the credentials environment.
            return UnsafeRemoteClient(source.plain_url, **env)

        return svn.remote.RemoteClient(source.url, **env)

    @classmethod
    def from_source(cls, source: Source, repo_directory: PathLike,
                    **kwargs: Any) -> 'Subversion_Repository':
        """
        Initialize a Subversion repository from its `Source` domain object.

        This does not require a checkout of the repository, and instead
        communicates solely with the server.
        """

        repository = cls(source, repo_directory, **kwargs)
        repository.repo = cls._create_remote_repo(source)
        return repository

    @classmethod
    def get_branches(cls, source: Source) -> List[str]:
        repo = cls._create_remote_repo(source)
        try:
            return [
                str(path).rstrip('/') for path in repo.list(rel_path='branches')
            ]
        except svn.exception.SvnException as error:
            raise RepositorySourceException('Could not retrieve branches') from error

    @property
    def repo(self) -> svn.common.CommonClient:
        if self._repo is None:
            path = self._repo_directory.expanduser()
            env = self._create_environment(self.source)
            self._repo = svn.local.LocalClient(str(path), **env)

        return self._repo

    @repo.setter
    def repo(self, repo: object) -> None:
        if not isinstance(repo, svn.common.CommonClient):
            raise TypeError('Repository must be a PySvn Client instance')

        self._repo = repo

    @property
    def version_info(self) -> Tuple[int, ...]:
        if self._version_info is None:
            version = self.repo.run_command('--version', ['--quiet'])[0]
            self._version_info = tuple(
                int(number) for number in str(version).split('.')
                if number.isdigit()
            )

        return self._version_info

    def is_empty(self) -> bool:
        try:
            self.repo.info()
        except svn.exception.SvnException:
            return True
        else:
            return False

    def update(self, shallow: bool = False, checkout: bool = True,
               branch: Optional[str] = None) -> None:
        # pylint: disable=no-member
        if not isinstance(self.repo, svn.local.LocalClient):
            raise TypeError('Repository has no local client, check out the repository first')
        if branch is not None:
            self.checkout(shallow=shallow, branch=branch)

        try:
            self.repo.update()
        except svn.exception.SvnException as error:
            raise RepositorySourceException('Could not update repository') from error

    def checkout(self, paths: Optional[Sequence[str]] = None,
                 shallow: bool = False, branch: Optional[str] = None) -> None:
        if not isinstance(self.repo, svn.remote.RemoteClient):
            raise TypeError('Repository is already local, update the repository instead')

        # Check out trunk directory
        args = [f'{self.repo.url}/trunk', str(self._repo_directory)]
        if paths is not None:
            args.extend(['--depth', 'immediates'])

        try:
            self.repo.run_command('checkout', args)
        except svn.exception.SvnException as error:
            raise RepositorySourceException('Could not checkout repository') from error

        # Invalidate so that we may continue woorking with a local client
        self._repo = None

        # Check out sparse subdirectories if there are paths
        if paths is not None:
            self.checkout_sparse(paths)

    def checkout_sparse(self, paths: Sequence[str], remove: bool = False,
                        shallow: bool = False, branch: Optional[str] = None) -> None:
        if remove:
            depth = 'empty'
        else:
            depth = 'infinity'

        for path in paths:
            full_path = str(self._repo_directory / path)
            try:
                self.repo.run_command('update',
                                      ['--set-depth', depth, full_path])
            except svn.exception.SvnException as error:
                raise RepositorySourceException('Could not sparse checkout') from error

    @staticmethod
    def parse_svn_revision(rev: Optional[Version], default: str) -> str:
        """
        Convert a Subversion revision `rev` to a supported revision. Removes the
        leading 'r' if it is present. 'HEAD' is also allowed. If `rev` is
        `None`, then `default` is used instead. Raises a `ValueError` if the
        revision number cannot be converted.
        """

        if rev is None:
            rev = default
        else:
            rev = str(rev)

        if rev.startswith('r'):
            rev = rev[1:]
        elif rev == 'HEAD':
            return rev

        return str(int(rev))

    def _query(self, filename: str, from_revision: Version,
               to_revision: Version) -> Iterator[LogEntry]:
        try:
            return self.repo.log_default(rel_filepath=filename,
                                         revision_from=from_revision,
                                         revision_to=to_revision,
                                         limit=self._iterator_limiter.size)
        except svn.exception.SvnException as error:
            raise RepositoryDataException('Could not search revisions') from error

    def get_data(self, from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None, force: bool = False,
                 **kwargs: Any) -> List[Dict[str, str]]:
        versions = super().get_data(from_revision, to_revision, force=force,
                                    **kwargs)

        self._parse_tags()

        return versions

    def get_versions(self, filename: str = 'trunk',
                     from_revision: Optional[Version] = None,
                     to_revision: Optional[Version] = None,
                     descending: bool = False, **kwargs: Any) -> List[Dict[str, str]]:
        """
        Retrieve data about each version of a specific file path `filename`.

        The range of the log to retrieve can be set with `from_revision` and
        `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default).
        """

        from_revision = self.parse_svn_revision(from_revision, '1')
        to_revision = self.parse_svn_revision(to_revision, 'HEAD')

        versions = []
        log_descending = None
        self._reset_limiter()
        try:
            log = self._query(filename, from_revision, to_revision)
            had_versions = True
            while self._iterator_limiter.check(had_versions):
                had_versions = False
                for entry in log:
                    had_versions = True
                    new_version = self._parse_version(entry, filename=filename,
                                                      **kwargs)
                    versions.append(new_version)

                count = self._iterator_limiter.size + self._iterator_limiter.skip
                self._iterator_limiter.update()
                if self._iterator_limiter.check(had_versions):
                    logging.info('Analysed batch of revisions, now at %d (r%s)',
                                 count, versions[-1]['version_id'])

                    # Check whether the log is being followed in a descending
                    # order for reordering the result
                    if log_descending is None and len(versions) > 1:
                        log_descending = int(versions[-2]['version_id']) > \
                                         int(versions[-1]['version_id'])

                    # Update the revision range. Because Subversion does not
                    # allow logs on ranges where the target path does not
                    # exist, always keep the latest revision within the range
                    # but trim it off.
                    from_revision = versions[-1]['version_id']
                    log = self._query(filename, from_revision, to_revision)
                    try:
                        next(log)
                    except StopIteration:
                        break
        except svn.exception.SvnException as error:
            raise RepositoryDataException('Could not analyze revisions') from error

        # Sort the log if it is not already in the preferred order
        if descending == log_descending:
            return versions

        return sorted(versions, key=lambda version: version['version_id'],
                      reverse=descending)

    def _parse_version(self, commit: LogEntry, stats: bool = True,
                       **kwargs: Any) -> Dict[str, str]:
        # Convert to local timestamp
        commit_date = commit.date.replace(tzinfo=dateutil.tz.tzutc())
        commit_datetime = commit_date.astimezone(dateutil.tz.tzlocal())
        message = commit.msg if commit.msg is not None else ''
        version = {
            # Primary data
            'repo_name': str(self._repo_name),
            'version_id': str(commit.revision),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(message),
            'type': 'commit',
            'developer': commit.author,
            'developer_username': commit.author,
            'developer_email': str(0),
            'commit_date': format_date(commit_datetime),
            'author_date': str(0)
        }

        if stats:
            diff_stats = self.get_diff_stats(to_revision=version['version_id'],
                                             **kwargs)
            version.update(diff_stats)

        return version

    def get_diff_stats(self, filename: str = '',
                       from_revision: Optional[Version] = None,
                       to_revision: Optional[Version] = None) -> Dict[str, str]:
        """
        Retrieve statistics about the difference between two revisions.

        Exceptions that are the result of the svn command failing are logged
        and the return value is a dictionary with zero values.
        """

        if isinstance(self.repo, svn.remote.RemoteClient):
            path = f'{self.repo.url}/{filename}'
        else:
            path = str(self._repo_directory / filename)

        diff = Difference(self, path, from_revision=from_revision,
                          to_revision=to_revision)
        stats = diff.execute()
        stats['branch'] = str(0)
        self._tables['change_path'].extend(diff.change_paths.get())

        return stats

    def _parse_tags(self) -> None:
        try:
            for tag in self.repo.list(extended=True, rel_path='tags'):
                if not isinstance(tag, str):
                    self._parse_tag(tag)
        except svn.exception.SvnException:
            logging.exception('Could not retrieve tags')

    def _parse_tag(self, tag: Dict[str, Union[int, str, datetime]]) -> None:
        # Convert to local timestamp
        if isinstance(tag['date'], datetime):
            tagged_date = tag['date'].replace(tzinfo=dateutil.tz.tzutc())
            tagged_datetime = tagged_date.astimezone(dateutil.tz.tzlocal())
        else:
            tagged_datetime = datetime.fromtimestamp(0)

        self._tables['tag'].append({
            'repo_name': str(self._repo_name),
            'tag_name': str(tag['name']).rstrip('/'),
            'version_id': str(tag['commit_revision']),
            'message': str(0),
            'tagged_date': format_date(tagged_datetime),
            'tagger': str(tag['author']),
            'tagger_email': str(0)
        })

    def get_contents(self, filename: str,
                     revision: Optional[Version] = None) -> bytes:
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        try:
            return self.repo.cat(filename, revision=revision)
        except svn.exception.SvnException as error:
            raise FileNotFoundException(f'Could not find file {filename}') from error

    def get_latest_version(self) -> Version:
        info = self.repo.info()
        return int(info['entry_revision'])
