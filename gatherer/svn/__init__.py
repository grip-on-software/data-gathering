"""
Module for parsing Subversion repositories.
"""

import datetime
import os.path
# Non-standard imports
import dateutil.tz
import svn.local
import svn.remote

from ..utils import parse_unicode, Sprint_Data
from ..version_control import Version_Control_Repository

__all__ = ["Subversion_Repository"]

class Subversion_Repository(Version_Control_Repository):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    def __init__(self, repo_name, repo_directory, **kwargs):
        super(Subversion_Repository, self).__init__(repo_name, repo_directory, **kwargs)
        self.svn = svn.local.LocalClient(os.path.expanduser(repo_directory))

    @classmethod
    def from_url(cls, repo_name, repo_directory, url):
        """
        Initialize a Subversion repository from its checkout URL.
        """

        repository = cls(repo_name, repo_directory)
        repository.svn = svn.remote.RemoteClient(url)
        return repository

    def get_versions(self, filename='', from_revision=None, to_revision=None, descending=False):
        """
        Retrieve data about each version of a specific file path `filename`.

        The range of the log to retrieve can be set with `from_revision` and
        `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default).
        """

        versions = []
        log = self.svn.log_default(rel_filepath=filename,
                                   revision_from=from_revision,
                                   revision_to=to_revision)
        for entry in log:
            # Convert to local timestamp
            commit_date = entry.date.replace(tzinfo=dateutil.tz.tzutc())
            commit_date = commit_date.astimezone(dateutil.tz.tzlocal())
            message = entry.msg if entry.msg is not None else ''
            version = {
                # Primary data
                'svn_repo': str(self.repo_name),
                'revision': str(entry.revision),
                'sprint_id': str(0),
                # Additional data
                'developer': entry.author,
                'message': parse_unicode(message),
                'commit_date': datetime.datetime.strftime(commit_date, '%Y-%m-%d %H:%M:%S')
            }

            if self.retrieve_stats:
                version.update(self.get_diff_stats(to_revision=version['revision']))

            versions.append(version)

        return sorted(versions, key=lambda version: version['revision'],
                      reverse=descending)

    def get_diff_stats(self, from_revision=None, to_revision=None):
        """
        Retrieve statistics about the difference between two revisions.
        """

        if from_revision is None and to_revision is None:
            args = []
        else:
            if from_revision is None:
                from_revision = int(to_revision)-1
            elif to_revision is None:
                to_revision = int(from_revision)+1

            args = [
                '--old', self.repo_directory + '@' + from_revision,
                '--new', self.repo_directory + '@' + to_revision
            ]

        diff_result = self.svn.run_command('diff', args)

        insertions = 0
        deletions = 0
        number_of_lines = 0
        number_of_files = 0
        size = 0
        for line in diff_result:
            if line.startswith('==='):
                head = True
                number_of_files += 1
            elif head and line.startswith('@@ '):
                head = False

            if not head:
                insertions += line.startwith('+')
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

        return self.svn.cat(filename, revision=revision)
