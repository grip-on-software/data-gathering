"""
Utilities for various parts of the data gathering chain.

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

import bisect
import json
import logging
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING
import dateutil.parser
import dateutil.tz
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .domain import Project
else:
    Project = object

class Iterator_Limiter:
    """
    Class which keeps handles batches of queries and keeps track of iterator
    count, in order to limit batch processing.
    """

    def __init__(self, size: int = 1000, maximum: int = 10000000) -> None:
        self._skip = 0
        self._page = 1
        self._size = size
        self._max = maximum

    def check(self, had_content: bool) -> bool:
        """
        Check whether a loop condition to continue retrieving iterator data
        should still evaluate to true.
        """

        if had_content and self._size != 0 and not self.reached_limit():
            return True

        return False

    def reached_limit(self) -> bool:
        """
        Check whether the hard limit of the iterator limiter has been reached.
        """

        if self._skip + self._size > self._max:
            return True

        return False

    def update(self) -> None:
        """
        Update the iterator counter after a batch, to prepare the next query.
        """

        self._skip += self._size
        self._page += 1
        if self.reached_limit():
            self._size = self._max - self._skip

    @property
    def size(self) -> int:
        """
        Retrieve the size of the next batch query.
        """

        return self._size

    @property
    def page(self) -> int:
        """
        Retrieve the 1-indexed page number which the iterator is to obtain next.
        """

        return self._page

    @property
    def skip(self) -> int:
        """
        Retrieve the current iterator counter.
        """

        return self._skip

class Sprint_Data:
    """
    Object that loads sprint data and allows matching timestamps to sprints
    based on their date ranges.

    Only works after jira_to_json.py has retrieved the sprint data or if
    a `sprints` argument is provided.
    """

    def __init__(self, project: Project,
                 sprints: Optional[Sequence[Dict[str, str]]] = None) -> None:
        if sprints is not None:
            self._data = deepcopy(sprints)
        else:
            self._data = self._import_sprints(project)

        self._sprint_ids: List[int] = []
        self._start_dates: List[datetime] = []
        self._end_dates: List[datetime] = []

        for sprint in self.get_sorted_sprints():
            self._sprint_ids.append(int(sprint['id']))
            self._start_dates.append(get_local_datetime(sprint['start_date']))
            self._end_dates.append(get_local_datetime(sprint['end_date']))

    @staticmethod
    def _import_sprints(project: Project) -> List[Dict[str, str]]:
        sprint_filename = Path(project.export_key, 'data_sprint.json')

        if sprint_filename.exists():
            with sprint_filename.open('r', encoding='utf-8') as sprint_file:
                return json.load(sprint_file)
        else:
            logging.warning('Could not load sprint data, no sprint matching possible.')
            return []

    def get_sorted_sprints(self) -> List[Dict[str, str]]:
        """
        Retrieve the list of sprints sorted on start date.
        """

        return sorted(self._data, key=lambda sprint: sprint['start_date'])

    def find_sprint(self, time: datetime,
                    sprint_ids: Optional[Sequence[int]] = None) -> Optional[int]:
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

    def _bisect(self, time: datetime,
                sprint_ids: Optional[Sequence[int]] = None,
                overlap: bool = False, end: Optional[int] = None) -> Optional[int]:
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

        # Return the suitable sprint ID.
        return sprint_id

GATHERER_DATETIME_PATTERN = re.compile(r"^\d\d\d\d-\d\d-\d\d(?: \d\d:\d\d:\d\d)?$")

def get_datetime(date: str, date_format: str = '%Y-%m-%d %H:%M:%S') -> datetime:
    """
    Convert a date string to a `datetime` object without a timezone.

    The date string has a standard YYYY-MM-DD HH:MM:SS format or another
    parseable `date_format`. This is essentially a wrapper around
    `datetime.strptime` but with a default format.
    """

    return datetime.strptime(date, date_format)

def get_local_datetime(date: str, date_format: str = '%Y-%m-%d %H:%M:%S') -> datetime:
    """
    Convert a date string to a `datetime` object with the local timezone.

    The date string has a standard YYYY-MM-DD HH:MM:SS format or another
    parseable `date_format`.
    """

    parsed_date = get_datetime(date, date_format)
    return parsed_date.replace(tzinfo=dateutil.tz.tzlocal())

def get_utc_datetime(date: str, date_format: str = '%Y-%m-%d %H:%M:%S') -> datetime:
    """
    Convert a date string to a `datetime` object with the UTC timezone.

    The date string has a standard YYYY-MM-DD HH:MM:SS format or another
    parseable `date_format`.
    """

    parsed_date = get_datetime(date, date_format)
    return parsed_date.replace(tzinfo=dateutil.tz.tzutc())

def convert_local_datetime(date: datetime) -> datetime:
    """
    Convert a datetime object `date` to one that is in the local timezone.
    If the date did not have a timezone then the local timezone is made explicit
    (without adjustment of time).
    """

    return date.astimezone(dateutil.tz.tzlocal())

def convert_utc_datetime(date: datetime) -> datetime:
    """
    Convert a datetime object `date` to one that is in the UTC timezone.
    If the date did not have a timezone then it is assumed to be in the system
    local time and is adjusted to UTC time.
    """

    return date.astimezone(dateutil.tz.tzutc())

def format_date(date: datetime, date_format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format a datetime object in a standard YYYY-MM-DD HH:MM:SS format or
    another applicable `date_format`.
    """

    return date.strftime(date_format)

def parse_utc_date(date: str) -> str:
    """
    Convert a ISO8601 date string to a standard date string.
    The date string must have a zone identifier.

    The standard format used by the gatherer is YYYY-MM-DD HH:MM:SS.
    """

    zone_date = dateutil.parser.parse(date)
    return format_date(convert_local_datetime(zone_date))

def parse_date(date: str) -> str:
    """
    Convert a date string from sources like JIRA to a standard date string,
    excluding milliseconds and zone information, and using spaces to
    separate fields instead of 'T'.

    This function does not account for time zones and assumes that the date
    is a local date, even if it is trailed by a zone identifier.

    The standard format used by the gatherer is YYYY-MM-DD HH:MM:SS.
    Additionally, dates of the format YYYY-MM-DD are also allowed.

    If the date cannot be parsed into the standard format, then the lowest
    timestamp that is still accepted by datetime methods, '1900-01-01 00:00:00',
    is returned.
    """

    date_string = str(date).replace('T', ' ').split('+', 1)[0].split('.', 1)[0]
    date_string = date_string.rstrip('Z')
    if not GATHERER_DATETIME_PATTERN.match(date_string):
        return "1900-01-01 00:00:00"

    return date_string

def parse_unicode(text: str) -> str:
    """
    Convert unicode `text` to a string without invalid unicode characters.
    """

    data = text.encode('utf-8', 'replace')
    return data.decode('utf-8', 'replace')
