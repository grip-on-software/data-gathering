"""
Updated time trackers
"""

from builtins import object
import os
from datetime import datetime

class Updated_Time(object):
    """
    Tracker for the latest update time from which we query for newly updated
    issues.
    """

    def __init__(self, timestamp):
        self._timestamp = timestamp
        self._date = datetime.strptime(self._timestamp, '%Y-%m-%d %H:%M')

    def is_newer(self, timestamp, timestamp_format='%Y-%m-%d %H:%M:%S'):
        """
        Check whether a given `timestamp`, a string which is formatted according
        to `timestamp_format`, is newer than the update date.
        """

        if self._date < datetime.strptime(timestamp, timestamp_format):
            return True

        return False

    @property
    def timestamp(self):
        """
        Retrieve the timestamp string of the latest update.
        """

        return self._timestamp

    @property
    def date(self):
        """
        Return the datetime object of the latest update.
        """

        return self._date

class Update_Tracker(object):
    """
    Tracker for the update time which controls the storage of this timestamp.
    """

    def __init__(self, project, updated_since=None):
        self.updated_since = updated_since
        self.filename = os.path.join(project.export_key, 'jira-updated.txt')

    def get_updated_since(self):
        """
        Retrieve the latest update timestamp from a previous run.
        """

        if self.updated_since is None:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as update_file:
                    self.updated_since = update_file.read().strip()
            else:
                self.updated_since = "0001-01-01 01:01"

        return self.updated_since

    def save_updated_since(self, new_updated_since):
        """
        Store a new latest update time for later reuse.
        """

        with open(self.filename, 'w') as update_file:
            update_file.write(new_updated_since)
