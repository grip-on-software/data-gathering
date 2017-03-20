"""
Utilities for various parts of the data gathering chain.
"""

import bisect
import json
import logging
import os
from copy import deepcopy
from datetime import datetime
import dateutil.tz

class Iterator_Limiter(object):
    """
    Class which keeps handles batches of queries and keeps track of iterator
    count, in order to limit batch processing.
    """

    def __init__(self, size=1000, maximum=10000000):
        self._skip = 0
        self._size = size
        self._max = maximum

    def check(self, had_content):
        """
        Check whether a loop condition to continue retrieving iterator data
        should still evaluate to true.
        """

        if had_content and self._size != 0 and not self.reached_limit():
            return True

        return False

    def reached_limit(self):
        """
        Check whether the hard limit of the iterator limiter has been reached.
        """

        if self._skip + self._size > self._max:
            return True

        return False

    def update(self):
        """
        Update the iterator counter after a batch, to prepare the next query.
        """

        self._skip += self._size
        if self.reached_limit():
            self._size = self._max - self._skip

    @property
    def size(self):
        """
        Retrieve the size of the next batch query.
        """

        return self._size

    @property
    def skip(self):
        """
        Retrieve the current iterator counter.
        """

        return self._skip

class Sprint_Data(object):
    """
    Object that loads sprint data and allows matching timestamps to sprints
    based on their date ranges.

    Only works after jira_to_json.py has retrieved the sprint data or if
    a `sprints` argument is provided.
    """

    def __init__(self, project, sprints=None):
        if sprints is not None:
            self._data = deepcopy(sprints)
        else:
            self._data = self._import_sprints(project)

        self._sprint_ids = []
        self._start_dates = []
        self._end_dates = []

        for sprint in self.get_sorted_sprints():
            self._sprint_ids.append(int(sprint['id']))
            self._start_dates.append(get_local_datetime(sprint['start_date']))
            self._end_dates.append(get_local_datetime(sprint['end_date']))

    @staticmethod
    def _import_sprints(project):
        sprint_filename = os.path.join(project.export_key, 'data_sprint.json')

        if os.path.exists(sprint_filename):
            with open(sprint_filename, 'r') as sprint_file:
                return json.load(sprint_file)
        else:
            logging.warning('Could not load sprint data, no sprint matching possible.')
            return []

    def get_sorted_sprints(self):
        """
        Retrieve the list of sprints sorted on start date.
        """

        return sorted(self._data, key=lambda sprint: sprint['start_date'])

    def find_sprint(self, time, sprint_ids=None):
        """
        Retrieve a sprint ID of a sprint that encompasses the given `time`,
        which is a `datetime` object or a date string in standard
        YYYY-MM-DD HH-MM-SS format.

        If `sprint_ids` is given, then only consider the given sprint IDs for
        matching. If no sprint exists according to these criteria, then `None`
        is returned.
        """

        if isinstance(time, datetime):
            if time.tzinfo is None or time.tzinfo.utcoffset(time) is None:
                time = time.replace(tzinfo=dateutil.tz.tzlocal())
        else:
            time = get_local_datetime(time)

        return self._bisect(time, sprint_ids=sprint_ids, overlap=True)

    def _bisect(self, time, sprint_ids=None, overlap=False, end=None):
        if end is None:
            end = len(self._start_dates)

        # Find start date
        index = bisect.bisect_right(self._start_dates, time, hi=end)
        if index == 0:
            # Older than all sprints
            return None

        # Check end date
        if time > self._end_dates[index-1]:
            # The moment is not actually encompassed inside this sprint.
            # Either it is actually later than the sprint end, or there are
            # partially overlapping sprints that interfere. Try the former
            # sprint that starts earlier it see if it and overlaps, but do not
            # try to search further if that fails.
            if overlap and index > 1 and time <= self._end_dates[index-2]:
                index = index-1
            else:
                return None

        # We found a sprint that encompasses the time moment. Check whether
        # this sprint is within the list of allowed IDs before returning it.
        sprint_id = self._sprint_ids[index-1]
        if sprint_ids is not None and sprint_id not in sprint_ids:
            # Attempt to find a sprint that started earlier than this one, but
            # overlaps in such as way that the time is within that sprint.
            # We do not need to search for later sprints since they will always
            # have a later start time than the time we search for, due to the
            # right bisection search we use.
            return self._bisect(time, sprint_ids=sprint_ids, overlap=False,
                                end=index-1)
        else:
            return sprint_id

def get_local_datetime(date, date_format='%Y-%m-%d %H:%M:%S'):
    """
    Convert a date string to a `datetime` object with the local timezone.

    The date string has a standard YYYY-MM-DD HH:MM:SS format or another
    parseable `date_format`.
    """

    parsed_date = datetime.strptime(date, date_format)
    return parsed_date.replace(tzinfo=dateutil.tz.tzlocal())

def parse_date(date):
    """
    Convert a date string from sources like JIRA to a standard date string,
    excluding milliseconds and using spaces to separate fields instead of 'T'.
    The standard format is YYYY-MM-DD HH:MM:SS.

    If the date cannot be parsed, '0' is returned.
    """

    date_string = str(date)
    date_string = date_string.replace('T', ' ')
    date_string = date_string.split('.', 1)[0]
    if date_string is None:
        return "0"

    return date_string

def parse_unicode(text):
    """
    Convert unicode `text` to a string without unicode characters.
    """

    if isinstance(text, unicode):
        return text.encode('utf8', 'replace')

    return str(text)

def parse_svn_revision(rev):
    """
    Convert a Subversion revision number to an integer. Removes the leading 'r'
    if it is present.
    """

    if rev.startswith('r'):
        rev = rev[1:]

    return int(rev)
