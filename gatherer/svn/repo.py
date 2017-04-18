"""
Module that handles access to and remote updates of a Subversion repository.
"""

from builtins import str
import logging
import os.path
# Non-standard imports
import dateutil.tz
import svn.common
import svn.local
import svn.remote

from .difference import Difference
from ..table import Table, Key_Table
from ..utils import format_date, parse_unicode, Iterator_Limiter
from ..version_control import Version_Control_Repository

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
            'tag': Key_Table('tag', 'tag_name')
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
        except svn.common.SvnException:
            return True
        else:
            return False

    def _query(self, filename, from_revision, to_revision):
        return self.repo.log_default(rel_filepath=filename,
                                     revision_from=from_revision,
                                     revision_to=to_revision,
                                     limit=self._iterator_limiter.size)

    def get_data(self, **kwargs):
        versions = super(Subversion_Repository, self).get_data(**kwargs)

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

        if from_revision is None:
            from_revision = '1'
        if to_revision is None:
            to_revision = 'HEAD'

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

    def _parse_version(self, entry, filename='', stats=True, **kwargs):
        # Convert to local timestamp
        commit_date = entry.date.replace(tzinfo=dateutil.tz.tzutc())
        commit_datetime = commit_date.astimezone(dateutil.tz.tzlocal())
        message = entry.msg if entry.msg is not None else ''
        version = {
            # Primary data
            'repo_name': str(self._repo_name),
            'version_id': str(entry.revision),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(message),
            'type': 'commit',
            'developer': entry.author,
            'developer_email': str(0),
            'commit_date': format_date(commit_datetime)
        }

        if stats:
            diff_stats = self.get_diff_stats(filename=filename,
                                             to_revision=version['version_id'])
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
        except svn.common.SvnException:
            logging.exception('Could not retrieve tags')

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        return self.repo.cat(filename, revision=revision)

    def get_latest_version(self):
        info = self.repo.info()
        return info['entry_revision']
