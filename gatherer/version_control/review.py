"""
Module for a code review system which has an API that allows retrieving merge
requests and commit comments, in addition to the usual version information from
the repository itself.

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

from abc import abstractmethod
from datetime import datetime
from typing import Any, Optional, Tuple, TYPE_CHECKING
import dateutil.tz
from ..table import Table, Key_Table, Link_Table
from ..utils import convert_local_datetime, format_date, get_local_datetime
from ..version_control.repo import Version_Control_Repository, PathLike, Version, Tables
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
else:
    Project = object
    Source = object

class Review_System(Version_Control_Repository):
    """
    Abstract class for a code review system which has an API that allows
    retrieving merge requests and commit comments, in addition to the usual
    version information from the repository itself.

    Subclasses that implement this class must also implement another actual
    version control system.
    """

    AUXILIARY_TABLES = {"merge_request", "merge_request_note", "commit_comment"}

    @abstractmethod
    def __init__(self, source: Source, repo_directory: PathLike,
                 project: Optional[Project] = None, **kwargs: Any) -> None:
        super().__init__(source, repo_directory, project=project, **kwargs)

        if self.UPDATE_TRACKER_NAME is None:
            raise NotImplementedError('Review_System subclass must define UPDATE_TRACKER_NAME')

        self._tables.update(self.review_tables)

        self._update_trackers[self.UPDATE_TRACKER_NAME] = self.null_timestamp
        self._tracker_date: Optional[datetime] = None
        self._latest_date: Optional[datetime] = None

    @classmethod
    def get_compare_url(cls, source: Source, first_version: Version,
                        second_version: Optional[Version] = None) -> Optional[str]:
        # pylint: disable=unused-argument
        """
        Create a URL to compare two versions at the remote repository located
        at `source`. The `first_version` is the version to start comparing at
        and the `second_version` is the version to stop comparing, or `None`
        to compare against the latest main branch version.

        This method returns a URL based on source information and the version
        control system type. If no such URL can be provided for the source,
        then this method returns `None`.
        """

        return None

    @classmethod
    def get_tree_url(cls, source: Source, version: Optional[Version] = None,
                     path: Optional[str] = None, line: Optional[int] = None) -> Optional[str]:
        # pylint: disable=unused-argument
        """
        Create a URL to show the state of the repository at `source`.
        The `version` is the version to show the state of, or `None` to show
        the latest main branch version. If `path` is provided, then the
        state of the file or directory at this version is shown. Additionally,
        if `line` is provided, then the URL will display the given line number
        of the file if possible.

        This method returns a URL based on source information and the version
        control system type. If no such URL can be provided for the source,
        then this method returns `None`.
        """

        return None

    def set_update_tracker(self, file_name: str, value: str) -> None:
        super().set_update_tracker(file_name, value)
        self._tracker_date = None
        self._latest_date = None

    def set_latest_date(self) -> None:
        """
        Alter the update tracker to match the latest date found.
        """

        if self.UPDATE_TRACKER_NAME is None:
            return

        if self._latest_date is not None:
            latest_date = format_date(convert_local_datetime(self._latest_date))
            self._update_trackers[self.UPDATE_TRACKER_NAME] = latest_date

    @property
    def tracker_date(self) -> datetime:
        """
        Retrieve the update tracker's timestamp as a datetime object.
        """

        if self._tracker_date is None:
            if self.UPDATE_TRACKER_NAME is None:
                update_tracker = self.null_timestamp
            else:
                update_tracker = self._update_trackers[self.UPDATE_TRACKER_NAME]

            self._tracker_date = get_local_datetime(update_tracker)

        return self._tracker_date

    def _is_newer(self, date: datetime) -> bool:
        if self._latest_date is None:
            self._latest_date = self.tracker_date

        if date.tzinfo is None:
            date = date.replace(tzinfo=dateutil.tz.tzutc())

        if date > self.tracker_date:
            self._latest_date = max(date, self._latest_date)
            return True

        return False

    @staticmethod
    def build_user_fields(field: str) -> Tuple[str, str]:
        """
        Retrieve a tuple of fields that are related to a single user field.
        The tuple contains the field itself as well as any personally
        identifiable fields obtainable from the review system API.
        """

        return (field, f'{field}_username')

    @property
    def review_tables(self) -> Tables:
        """
        Retrieve the tables that are populated with the review system API result
        information. Subclasses may override this method to add more tables to
        the dictionary, which is added to the version control system tables
        upon construction.
        """

        author = self.build_user_fields('author')
        assignee = self.build_user_fields('assignee')
        return {
            "merge_request": Key_Table('merge_request', 'id',
                                       encrypt_fields=author + assignee),
            "merge_request_note": Link_Table('merge_request_note',
                                             ('merge_request_id', 'note_id'),
                                             encrypt_fields=author),
            "commit_comment": Table('commit_comment', encrypt_fields=author)
        }

    @property
    def null_timestamp(self) -> str:
        """
        Retrieve a timestamp string to use as a default, when no timestamp is
        known, in contexts where we wish to compare against other timestamps
        and have the other timestamp win the comparison. This must still be
        parseable to a valid date.
        """

        return "0001-01-01 01:01:01"
