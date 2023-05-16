"""
Module for parsing Subversion difference formats.

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

import logging
from typing import Dict, Optional, TYPE_CHECKING
import svn.exception
from ..version_control.repo import Change_Type, Version
from ..table import Table
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .repo import Subversion_Repository
else:
    Subversion_Repository = object

class Difference_State:
    """
    Tracking object for the current state of the difference parser through
    token updates from the parser.
    """

    def __init__(self, diff: 'Difference') -> None:
        self._diff = diff

        self._file: Optional['Difference_File'] = None
        self._insertions = 0
        self._deletions = 0
        self._number_of_files = 0
        self._size = 0
        self._head = True

    def parse_line(self, line: bytes) -> None:
        """
        Parse an untokenized line that the parser retrieved.
        """

        if line.startswith(b'Index: '):
            self._update_file()

            self._number_of_files += 1
            self._file = Difference_File(self._diff)
            self._file.parse_index(line)
        elif self._file is not None:
            if self._head:
                self._head = self._file.parse_head(line)
            else:
                self._file.parse_content(line)

    def _update_file(self) -> None:
        if self._file is not None:
            self._file.update_table()
            self._insertions += self._file.file_insertions
            self._deletions += self._file.file_deletions
            self._size += self._file.file_size

    def get_data(self) -> Dict[str, str]:
        """
        Retrieve the final information after processing the diff.
        """

        self._update_file()

        number_of_lines = self._insertions + self._deletions
        return {
            # Statistics
            'insertions': str(self._insertions),
            'deletions': str(self._deletions),
            'number_of_lines': str(number_of_lines),
            'number_of_files': str(self._number_of_files),
            'size': str(self._size)
        }

class Difference_File:
    """
    Tracking object for the current file-specific state of the difference
    parser through token updates from the difference-wide state.
    """

    # Tokens that occurs in the header of the file that indicate the old/new
    # file name after the token, as well as the old/new revision involved;
    # if the file does not exist in that revision, then it is an addition or
    # deletion depending on the token type as indicated here.
    HEAD_TOKENS = {
        b'---': Change_Type.ADDED,
        b'+++': Change_Type.DELETED
    }

    def __init__(self, diff: 'Difference') -> None:
        self._diff = diff
        self._filename = b''
        self._change_type = Change_Type.MODIFIED
        self._file_insertions = 0
        self._file_deletions = 0
        self._file_size = 0

    @property
    def file_insertions(self) -> int:
        """
        Retrieve the number of added lines in the diff for this file.
        """

        return self._file_insertions

    @property
    def file_deletions(self) -> int:
        """
        Retrieve the number of removed lines in the diff for this file.
        """

        return self._file_deletions

    @property
    def file_size(self) -> int:
        """
        Retrieve the number of bytes on changed lines in the file.
        """

        return self._file_size

    def parse_index(self, line: bytes) -> None:
        """
        Parse the index line containing the filename for this file.
        """

        self._filename = line[len(b'Index: '):]
        self._change_type = Change_Type.MODIFIED

    def parse_head(self, line: bytes) -> bool:
        """
        Parse the header in the difference of this file.

        Returns whether the header may still continue after this line.
        """

        for token, change_type in self.HEAD_TOKENS.items():
            if line.startswith(token):
                if line.endswith(b'(nonexistent)'):
                    self._change_type = change_type

                return True

        if line.startswith(b'@@ '):
            return False

        return True

    def parse_content(self, line: bytes) -> bool:
        """
        Parse a line with difference content for this file.

        Returns whether the line is actually part of the content.
        """

        if line.startswith(b'+'):
            self._file_insertions += 1
        elif line.startswith(b'-'):
            self._file_deletions += 1
        elif not line.startswith(b' '):
            return False

        self._file_size += len(line) - 1
        return True

    def update_table(self) -> None:
        """
        Update the table of file-based statistics.
        """

        if self._diff.version_id is not None:
            self._diff.change_paths.append({
                'repo_name': str(self._diff.repo.repo_name),
                'version_id': str(self._diff.version_id),
                'file': str(self._filename.decode('utf-8')),
                'change_type': str(self._change_type.value),
                'insertions': str(self._file_insertions),
                'deletions': str(self._file_deletions)
            })

class Difference:
    """
    Parser for Subversion difference format.
    """

    def __init__(self, repo: Subversion_Repository, path: str,
                 from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None) -> None:
        self._repo = repo
        self._path = path
        self._from_revision = from_revision
        self._to_revision = to_revision

        self._version_id: Optional[int] = None
        self._change_paths = Table('change_paths')

        if self._to_revision is not None and self._from_revision is None:
            self._from_revision = int(self._to_revision) - 1
            self._version_id = int(self._to_revision)
        elif self._from_revision is not None and self._to_revision is None:
            self._to_revision = int(self._from_revision) + 1

    def execute(self) -> Dict[str, str]:
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
                '-r', f'{self._from_revision}:{self._to_revision}'
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

        if not isinstance(diff_result, bytes):
            raise TypeError('Diff is not a bytes object')

        return self._parse_diff(diff_result)

    @property
    def repo(self) -> Subversion_Repository:
        """
        Retrieve the repository that this difference parser oprates on.
        """

        return self._repo

    @property
    def version_id(self) -> Optional[int]:
        """
        Retrieve the single version for which the differences is retrieved,
        in the case that the diff is made between its prior version and the
        version at hand. In other cases, this property returns `None`.
        """

        return self._version_id

    @property
    def change_paths(self) -> Table:
        """
        Retrieve the table of file-based statistics retrieved from the diff.
        """

        return self._change_paths

    def _parse_diff(self, diff_result: bytes) -> Dict[str, str]:
        state = Difference_State(self)
        for line in diff_result.splitlines():
            state.parse_line(line)

        return state.get_data()
