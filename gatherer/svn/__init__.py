"""
Module for parsing Subversion repositories.
"""

import datetime
import os.path
# Non-standard imports
import dateutil.tz
import svn.local

__all__ = ["Subversion_Repository"]

class Subversion_Repository(object):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    def __init__(self, path='.'):
        self.path = os.path.expanduser(path)
        self.svn = svn.local.LocalClient(self.path)

    def get_versions(self, filename, from_revision=None, to_revision=None, descending=False):
        """
        Retrieve data about each version of a specific file path `filename`.

        The range of the log to retrieve can be set with `from_revision` and
        `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default)
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
                'revision': str(entry.revision),
                'developer': entry.author,
                'message': message,
                'commit_date': datetime.datetime.strftime(commit_date, '%Y-%m-%d %H:%M:%S')
            }

            versions.append(version)

        return sorted(versions, key=lambda version: version['revision'],
                      reverse=descending)

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        return self.svn.cat(filename, revision=revision)
