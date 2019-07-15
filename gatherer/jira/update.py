"""
Updated time trackers
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from ..utils import get_datetime
from ..domain import Project

class Updated_Time:
    """
    Tracker for the latest update time from which we query for newly updated
    issues.
    """

    def __init__(self, timestamp: str) -> None:
        self._timestamp = timestamp
        self._date = get_datetime(self._timestamp, '%Y-%m-%d %H:%M')

    def is_newer(self, timestamp: str,
                 timestamp_format: str = '%Y-%m-%d %H:%M:%S') -> bool:
        """
        Check whether a given `timestamp`, a string which is formatted according
        to `timestamp_format`, is newer than the update date.
        """

        if self._date < get_datetime(timestamp, timestamp_format):
            return True

        return False

    @property
    def timestamp(self) -> str:
        """
        Retrieve the timestamp string of the latest update.
        """

        return self._timestamp

    @property
    def date(self) -> datetime:
        """
        Return the datetime object of the latest update.
        """

        return self._date

class Update_Tracker:
    """
    Tracker for the update time which controls the storage of this timestamp.
    """

    # Timestamp to use as a default for the update tracker and query.
    # This timestamp must be within the valid range for the Python 2 datetime's
    # strftime function, to ensure compatibility.
    NULL_TIMESTAMP = "1900-01-01 01:01"

    def __init__(self, project: Project, updated_since: Optional[str] = None) -> None:
        self.updated_since = updated_since
        self.filename = Path(project.export_key, 'jira-updated.txt')

    def get_updated_since(self) -> str:
        """
        Retrieve the latest update timestamp from a previous run.
        """

        if self.updated_since is None:
            if self.filename.exists():
                with self.filename.open('r') as update_file:
                    self.updated_since = update_file.read().strip()
            else:
                self.updated_since = self.NULL_TIMESTAMP

        return self.updated_since

    def save_updated_since(self, new_updated_since: str) -> None:
        """
        Store a new latest update time for later reuse.
        """

        with self.filename.open('w') as update_file:
            update_file.write(new_updated_since)
