"""
Utilities for various parts of the data gathering chain.
"""

import bisect
import json
from datetime import datetime

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

    Only works after jira_to_json.py has retrieved the sprint data.
    """

    def __init__(self, project):
        self._project = project

        with open(self._project + '/data_sprint.json', 'r') as sprint_file:
            self._data = json.load(sprint_file)

        self._sprint_ids = []
        self._start_dates = []
        self._end_dates = []
        self._date_format = '%Y-%m-%d %H:%M:%S'

        for sprint in self.get_sorted_sprints():
            self._sprint_ids.append(int(sprint['id']))
            self._start_dates.append(self._parse_date(sprint['start_date']))
            self._end_dates.append(self._parse_date(sprint['end_date']))

    def _parse_date(self, date):
        return datetime.strptime(date, self._date_format)

    def get_sorted_sprints(self):
        """
        Retrieve the list of sprints sorted on start date.
        """

        return sorted(self._data, key=lambda sprint: sprint['start_date'])

    def find_sprint(self, time):
        """
        Retrieve a sprint ID of a sprint that encompasses the given datetime
        object `time`. If not such sprint exists, `None` is returned.
        """

        # Find start date
        i = bisect.bisect_left(self._start_dates, time)
        if i == 0:
            # Older than all sprints
            return None

        # Find end date
        if time >= self._end_dates[i-1]:
            # Not actually inside this sprint (either later than the sprint
            # end, or partially overlapping sprints that interfere)
            return None

        return self._sprint_ids[i-1]

def parse_date(date):
    """
    Convert a date string from sources like JIRA to a standard date string,
    excluding milliseconds and using spaces to separate fields instead of 'T'.

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
