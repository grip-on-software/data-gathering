"""
Module that handles access to and remote updates of a Subversion repository.
"""

from builtins import str
import logging
import os.path
# Non-standard imports
import dateutil.tz
import svn.common
import svn.exception
import svn.local
import svn.remote

from .difference import Difference
from ..table import Table, Key_Table
from ..utils import format_date, parse_unicode, Iterator_Limiter
from ..version_control.repo import Version_Control_Repository, FileNotFoundException

class Subversion_Repository(Version_Control_Repository):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    def __init__(self, source, repo_directory, **kwargs):
        super(Subversion_Repository, self).__init__(source, repo_directory, **kwargs)
        self._repo = None
        self._version_info = None
        self._iterator_limiter = None
        self._reset_limiter()
        self._tables.update({
            'change_path': Table('change_path'),
            'tag': Key_Table('tag', 'tag_name',
                             encrypt_fields=('tagger', 'tagger_email'))
        })

    def _reset_limiter(self):
        self._iterator_limiter = Iterator_Limiter()

    @classmethod
    def from_source(cls, source, repo_directory, **kwargs):
        """
        Initialize a Subversion repository from its `Source` domain object.

        This does not require a checkout of the repository, and instead
        communicates solely with the server.
        """

        repository = cls(source, repo_directory, **kwargs)
        repository.repo = svn.remote.RemoteClient(source.url)
        return repository

    @property
    def repo(self):
        if self._repo is None:
            path = os.path.expanduser(self._repo_directory)
            self._repo = svn.local.LocalClient(path)

        return self._repo

    @repo.setter
    def repo(self, repo):
        if not isinstance(repo, svn.common.CommonClient):
            raise TypeError('Repository must be a PySvn Client instance')

        self._repo = repo

    @property
    def version_info(self):
        if self._version_info is None:
            version = self.repo.run_command('--version', ['--quiet'])[0]
            self._version_info = tuple(
                int(number) for number in version.split('.') if number.isdigit
            )

        return self._version_info

    def exists(self):
        return not self.is_empty()

    def is_empty(self):
        try:
            self.repo.info()
        except svn.exception.SvnException:
            return True
        else:
            return False

    def update(self, shallow=False, checkout=True):
        # pylint: disable=no-member
        if not isinstance(self.repo, svn.local.LocalClient):
            raise TypeError('Repository has no local client, check out the repository first')

        self.repo.update()

    def checkout(self, paths=None, shallow=False):
        if not isinstance(self.repo, svn.remote.RemoteClient):
            raise TypeError('Repository is already local, update the repository instead')

        # Check out trunk directory
        args = [self.source.url + '/trunk', self._repo_directory]
        if paths is not None:
            args.extend(['--depth', 'immediates'])

        self.repo.run_command('checkout', args)

        # Invalidate so that we may continue woorking with a local client
        self._repo = None

        # Check out sparse subdirectories if there are paths
        if paths is not None:
            self.checkout_sparse(paths)

    def checkout_sparse(self, paths, remove=False, shallow=False):
        if remove:
            depth = 'empty'
        else:
            depth = 'infinity'

        for path in paths:
            full_path = '{0}/{1}'.format(self._repo_directory, path)
            self.repo.run_command('update', ['--set-depth', depth, full_path])

    @staticmethod
    def parse_svn_revision(rev, default):
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

    def _query(self, filename, from_revision, to_revision):
        return self.repo.log_default(rel_filepath=filename,
                                     revision_from=from_revision,
                                     revision_to=to_revision,
                                     limit=self._iterator_limiter.size)

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        versions = super(Subversion_Repository, self).get_data(from_revision,
                                                               to_revision,
                                                               **kwargs)

        self._parse_tags()

        return versions

    def get_versions(self, filename='trunk', from_revision=None,
                     to_revision=None, descending=False, **kwargs):
        """
        Retrieve data about each version of a specific file path `filename`.

        The range of the log to retrieve can be set with `from_revision` and
        `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default).
        """

        from_revision = self.parse_svn_revision(from_revision, '1')
        to_revision = self.parse_svn_revision(to_revision, 'HEAD')

        versions = []
        self._reset_limiter()
        log = self._query(filename, from_revision, to_revision)
        log_descending = None
        had_versions = True
        while self._iterator_limiter.check(had_versions):
            had_versions = False
            for entry in log:
                had_versions = True
                new_version = self._parse_version(entry, filename=filename,
                                                  **kwargs)
                versions.append(new_version)

            count = self._iterator_limiter.size + self._iterator_limiter.skip
            if had_versions:
                logging.info('Analysed batch of revisions, now at %d (r%s)',
                             count, versions[-1]['version_id'])

            self._iterator_limiter.update()
            if self._iterator_limiter.check(had_versions):
                # Check whether the log is being followed in a descending order
                if log_descending is None and len(versions) > 1:
                    log_descending = int(versions[-2]['version_id']) > \
                                     int(versions[-1]['version_id'])

                # Update the revision range. Because Subversion does not allow
                # logs on ranges where the target path does not exist, always
                # keep the latest revision within the range but trim it off.
                from_revision = versions[-1]['version_id']
                log = self._query(filename, from_revision, to_revision)
                try:
                    next(log)
                except StopIteration:
                    break

        # Sort the log if it is not already in the preferred order
        if descending == log_descending:
            return versions

        return sorted(versions, key=lambda version: version['version_id'],
                      reverse=descending)

    def _parse_version(self, commit, stats=True, **kwargs):
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

    def get_diff_stats(self, filename='', from_revision=None, to_revision=None):
        """
        Retrieve statistics about the difference between two revisions.

        Exceptions that are the result of the svn command failing are logged
        and the return value is a dictionary with zero values.
        """

        if isinstance(self.repo, svn.remote.RemoteClient):
            path = self.repo.url + '/' + filename
        else:
            path = self._repo_directory + '/' + filename

        diff = Difference(self, path, from_revision=from_revision,
                          to_revision=to_revision)
        stats = diff.execute()
        stats['branch'] = str(0)
        self._tables['change_path'].extend(diff.change_paths.get())

        return stats

    def _parse_tags(self):
        try:
            for tag in self.repo.list(extended=True, rel_path='tags'):
                # Convert to local timestamp
                tagged_date = tag['date'].replace(tzinfo=dateutil.tz.tzutc())
                tagged_datetime = tagged_date.astimezone(dateutil.tz.tzlocal())

                self._tables['tag'].append({
                    'repo_name': str(self._repo_name),
                    'tag_name': tag['name'].rstrip('/'),
                    'version_id': str(tag['commit_revision']),
                    'message': str(0),
                    'tagged_date': format_date(tagged_datetime),
                    'tagger': tag['author'],
                    'tagger_email': str(0)
                })
        except svn.exception.SvnException:
            logging.exception('Could not retrieve tags')

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        try:
            return self.repo.cat(filename, revision=revision)
        except svn.exception.SvnException as error:
            raise FileNotFoundException(str(error))

    def get_latest_version(self):
        info = self.repo.info()
        return info['entry_revision']
