"""
Module for parsing Subversion repositories.
"""

import datetime
import logging
import os.path
# Non-standard imports
import dateutil.tz
import svn.common
import svn.local
import svn.remote

from ..utils import parse_unicode, Iterator_Limiter
from ..version_control import Version_Control_Repository

__all__ = ["Subversion_Repository"]

class Subversion_Repository(Version_Control_Repository):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    def __init__(self, repo_name, repo_directory, **kwargs):
        super(Subversion_Repository, self).__init__(repo_name, repo_directory, **kwargs)
        self._repo = None
        self._iterator_limiter = None
        self._reset_limiter()

    def _reset_limiter(self):
        self._iterator_limiter = Iterator_Limiter()

    @classmethod
    def from_url(cls, repo_name, repo_directory, url, **kwargs):
        """
        Initialize a Subversion repository from its checkout URL.
        """

        repository = cls(repo_name, repo_directory, **kwargs)
        repository.repo = svn.remote.RemoteClient(url)
        return repository

    @property
    def repo(self):
        if self._repo is None:
            path = os.path.expanduser(self.repo_directory)
            self._repo = svn.local.LocalClient(path)

        return self._repo

    @repo.setter
    def repo(self, repo):
        if not isinstance(repo, svn.common.CommonClient):
            raise TypeError('Repository must be a PySvn Client instance')

        self._repo = repo

    def is_empty(self):
        try:
            self.repo.info()
        except svn.common.SvnException:
            return False
        else:
            return True

    def _query(self, filename, from_revision, to_revision):
        return self.repo.log_default(rel_filepath=filename,
                                     revision_from=from_revision,
                                     revision_to=to_revision,
                                     limit=self._iterator_limiter.size)

    def get_versions(self, filename='', from_revision=None, to_revision=None, descending=False):
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
                new_version = self._parse_entry(entry)
                versions.append(new_version)

            count = self._iterator_limiter.size + self._iterator_limiter.skip
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
                    log.next()
                except StopIteration:
                    break

        # Sort the log if it is not already in the preferred order
        if descending == log_descending:
            return versions

        return sorted(versions, key=lambda version: version['version_id'],
                      reverse=descending)

    def _parse_entry(self, entry, filename=''):
        # Convert to local timestamp
        commit_date = entry.date.replace(tzinfo=dateutil.tz.tzutc())
        commit_datetime = commit_date.astimezone(dateutil.tz.tzlocal())
        message = entry.msg if entry.msg is not None else ''
        version = {
            # Primary data
            'repo_name': str(self.repo_name),
            'version_id': str(entry.revision),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(message),
            'type': 'commit',
            'developer': entry.author,
            'developer_email': '',
            'commit_date': datetime.datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')
        }

        if self.retrieve_stats:
            stats = self.get_diff_stats(filename=filename,
                                        to_revision=version['version_id'])
            version.update(stats)

        return version

    def get_diff_stats(self, filename='', from_revision=None, to_revision=None):
        """
        Retrieve statistics about the difference between two revisions.
        """

        if isinstance(self.repo, svn.remote.RemoteClient):
            path = self.repo.url + '/' + filename
        else:
            path = self.repo_directory + '/' + filename

        if from_revision is None and to_revision is None:
            args = [path]
        else:
            if from_revision is None:
                from_revision = int(to_revision)-1
            elif to_revision is None:
                to_revision = int(from_revision)+1

            args = [
                '-r', '{0}:{1}'.format(from_revision, to_revision), path
            ]

        diff_result = self.repo.run_command('diff', args)

        insertions = 0
        deletions = 0
        number_of_lines = 0
        number_of_files = 0
        size = 0
        head = True
        for line in diff_result:
            if line.startswith('==='):
                head = True
                number_of_files += 1
            elif head and line.startswith('@@ '):
                head = False

            if not head:
                insertions += line.startswith('+')
                deletions += line.startswith('-')
                size += len(line) - 1

        number_of_lines = insertions + deletions

        return {
            # Statistics
            'insertions': str(insertions),
            'deletions': str(deletions),
            'number_of_lines': str(number_of_lines),
            'number_of_files': str(number_of_files),
            'size': str(size)
        }

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        return self.repo.cat(filename, revision=revision)

    def get_latest_version(self):
        info = self.repo.info()
        return info['entry_revision']
