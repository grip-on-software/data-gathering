"""
Module for parsing Subversion difference formats.
"""

from builtins import object, str
import logging
import svn.exception
from ..version_control import Change_Type
from ..table import Table

class Difference(object):
    """
    Parser for Subversion difference format.
    """

    def __init__(self, repo, path, from_revision=None, to_revision=None):
        self._repo = repo
        self._path = path
        self._from_revision = from_revision
        self._to_revision = to_revision

        self._version_id = None
        self._change_paths = Table('change_paths')

        if self._from_revision is not None or self._to_revision is not None:
            if self._from_revision is None:
                self._from_revision = int(self._to_revision)-1
                self._version_id = self._to_revision
            elif self._to_revision is None:
                self._to_revision = int(self._from_revision)+1

    def execute(self):
        """
        Retrieve statistics from a difference.
        """

        # Ignore property changes since they are maintenance/automatic changes
        # that need not count toward diff changes.
        args = []
        if self._repo.version_info >= (1, 8):
            args.append('--ignore-properties')

        if self._from_revision is not None and self._to_revision is not None:
            args.extend([
                '-r', '{0}:{1}'.format(self._from_revision, self._to_revision)
            ])

        args.append(self._path)

        try:
            diff_result = self._repo.repo.run_command('diff', args,
                                                      return_binary=True)
        except svn.exception.SvnException:
            logging.exception('Could not retrieve diff')
            return {
                'insertions': str(0),
                'deletions': str(0),
                'number_of_lines': str(0),
                'number_of_files': str(0),
                'size': str(0)
            }

        return self._parse_diff(diff_result)

    @property
    def change_paths(self):
        """
        Retrieve the table of file-based statistics retrieved from the diff.
        """

        return self._change_paths

    def _parse_diff(self, diff_result):
        insertions = 0
        deletions = 0
        filename = None
        file_insertions = 0
        file_deletions = 0
        change_type = Change_Type.MODIFIED
        number_of_lines = 0
        number_of_files = 0
        size = 0
        head = True
        for line in diff_result.splitlines():
            if line.startswith(b'Index: '):
                if filename is not None:
                    self._parse_change_stats(filename, file_insertions,
                                             file_deletions)
                    insertions += file_insertions
                    deletions += file_deletions

                filename = line[len(b'Index: '):]
                file_insertions = 0
                file_deletions = 0
                change_type = Change_Type.MODIFIED
                head = True
            elif head:
                if line.startswith(b'---'):
                    if line.endswith('(nonexistent)'):
                        change_type = Change_Type.ADDED
                elif line.startswith(b'+++'):
                    if line.endswith('(nonexistent)'):
                        change_type = Change_Type.DELETED
                elif line.startswith(b'@@ '):
                    head = False

            if not head:
                if line.startswith(b'+'):
                    file_insertions += 1
                    size += len(line) - 1
                elif line.startswith(b'-'):
                    file_deletions += 1
                    size += len(line) - 1

        if filename is not None:
            self._parse_change_stats(filename, file_insertions, file_deletions)
            insertions += file_insertions
            deletions += file_deletions

        number_of_lines = insertions + deletions

        return {
            # Statistics
            'insertions': str(insertions),
            'deletions': str(deletions),
            'change_type': str(change_type.value),
            'number_of_lines': str(number_of_lines),
            'number_of_files': str(number_of_files),
            'size': str(size)
        }

    def _parse_change_stats(self, filename, file_insertions, file_deletions):
        if self._version_id is not None:
            self._change_paths.append({
                'repo_name': str(self._repo.repo_name),
                'version_id': str(self._version_id),
                'file': str(filename.decode('utf-8')),
                'insertions': str(file_insertions),
                'deletions': str(file_deletions)
            })
