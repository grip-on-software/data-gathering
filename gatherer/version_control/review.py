"""
Module for a code review system which has an API that allows retrieving merge
requests and commit comments, in addition to the usual version information from
the repository itself.
"""

from abc import abstractmethod
import dateutil.tz
from ..table import Table, Key_Table, Link_Table
from ..utils import convert_local_datetime, format_date, get_local_datetime
from ..version_control.repo import Version_Control_Repository

class Review_System(Version_Control_Repository):
    """
    Abstract class for a code review system which has an API that allows
    retrieving merge requests and commit comments, in addition to the usual
    version information from the repository itself.

    Subclasses that implement this class must also implement another actual
    version control system.
    """

    @abstractmethod
    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(Review_System, self).__init__(source, repo_directory,
                                            project=project, **kwargs)

        if self.UPDATE_TRACKER_NAME is None:
            raise NotImplementedError('Review_System subclass must define UPDATE_TRACKER_NAME')

        self._tables.update(self.review_tables)

        self._update_trackers[self.UPDATE_TRACKER_NAME] = self.null_timestamp
        self._tracker_date = None
        self._latest_date = None

    def set_update_tracker(self, file_name, value):
        super(Review_System, self).set_update_tracker(file_name, value)
        self._tracker_date = None
        self._latest_date = None

    def set_latest_date(self):
        """
        Alter the update tracker to match the latest date found.
        """

        if self._latest_date is not None:
            latest_date = format_date(convert_local_datetime(self._latest_date))
            self._update_trackers[self.UPDATE_TRACKER_NAME] = latest_date

    @property
    def tracker_date(self):
        """
        Retrieve the update tracker's timestamp as a datetime object.
        """

        if self._tracker_date is None:
            update_tracker = self._update_trackers[self.UPDATE_TRACKER_NAME]
            self._tracker_date = get_local_datetime(update_tracker)

        return self._tracker_date

    def _is_newer(self, date):
        if self._latest_date is None:
            self._latest_date = self.tracker_date

        if date.tzinfo is None:
            date = date.replace(tzinfo=dateutil.tz.tzutc())

        if date > self.tracker_date:
            self._latest_date = max(date, self._latest_date)
            return True

        return False

    @staticmethod
    def build_user_fields(field):
        """
        Retrieve a tuple of fields that are related to a single user field.
        The tuple contains the field itself as well as any personally
        identifiable fields obtainable from the review system API.
        """

        return (field, '{}_username'.format(field))

    @property
    def review_tables(self):
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
    def null_timestamp(self):
        """
        Retrieve a timestamp string to use as a default, when no timestamp is
        known, in contexts where we wish to compare against other timestamps
        and have the other timestamp win the comparison. This must still be
        parseable to a valid date.
        """

        return "0001-01-01 01:01:01"
