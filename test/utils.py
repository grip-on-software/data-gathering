"""
Tests for utilities for various parts of the data gatherer package.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
import dateutil.tz
from gatherer.domain.project import Project
from gatherer.utils import Iterator_Limiter, Sprint_Data, get_datetime, \
    get_local_datetime, convert_local_datetime, convert_utc_datetime, \
    format_date, parse_utc_date, parse_date, parse_unicode

class IteratorLimiterTest(unittest.TestCase):
    """
    Tests for class which handles batches of queries and tracks iterator count.
    """

    def setUp(self) -> None:
        self.limiter = Iterator_Limiter()

    def test_check(self) -> None:
        """
        Test checking whether to continue retrieving iterator data.
        """

        self.assertTrue(self.limiter.check(True))
        self.assertFalse(self.limiter.check(False))

    def test_reached_limit(self) -> None:
        """
        Test checking whether the hard limit has been reached.
        """

        self.assertFalse(self.limiter.reached_limit())

        limiter = Iterator_Limiter(size=1000, maximum=1000)
        limiter.update()
        self.assertTrue(limiter.reached_limit())

    def test_update(self) -> None:
        """
        Test updating the iterator counter after a batch.
        """

        self.limiter.update()
        self.assertEqual(self.limiter.skip, 1000)
        self.assertEqual(self.limiter.page, 2)

        limiter = Iterator_Limiter(size=1000, maximum=1000)
        limiter.update()
        self.assertEqual(limiter.size, 1)

class SprintDataTest(unittest.TestCase):
    """
    Tests for class that matches timestamps to sprints based on date ranges.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.data = [
            {
                "id": "1",
                "start_date": "2024-01-01 10:00:00",
                "end_date": "2024-02-01 10:00:00"
            },
            {
                "id": "2",
                "start_date": "2024-02-01 10:00:00",
                "end_date": "2024-03-01 10:00:00"
            },
            {
                "id": "3",
                "start_date": "2024-03-01 10:00:00",
                "end_date": "2024-04-01 10:00:00"
            },
            {
                "id": "4",
                "start_date": "2024-04-01 10:00:00",
                "end_date": "2024-05-01 10:00:00"
            }
        ]
        # Some shuffling in the data
        self.sprints = Sprint_Data(self.project, sprints=[
            self.data[1], self.data[0], self.data[3], self.data[2]
        ])

    def test_get_sorted_sprints(self) -> None:
        """
        Test retrieving the sprints sorted on start date.
        """

        self.assertEqual(self.sprints.get_sorted_sprints(), self.data)

        # If we need to load from a file and it does not exist, then no sprints
        # are available.
        with patch('gatherer.utils.Path', autospec=True) as path:
            attrs = {'exists.return_value': False}
            path.return_value.configure_mock(**attrs)
            sprints = Sprint_Data(self.project)
            self.assertEqual(sprints.get_sorted_sprints(), [])

    def test_find_sprint(self) -> None:
        """
        Test retrieving a sprint that encompassed the timestamp.
        """

        timestamps = [
            (datetime(2023, 12, 31, 12, 34, 56, tzinfo=timezone.utc), None),
            (datetime(2024, 2, 2, 10, 10, 10), 2),
            (datetime(2024, 2, 1, 10, 0, 0), 2),
            (datetime(2024, 4, 4, 10, 20, 30), 4),
            (datetime(2024, 5, 5, 12, 14, 16), None)
        ]
        for time, sprint_id in timestamps:
            with self.subTest(time=time):
                self.assertEqual(self.sprints.find_sprint(time), sprint_id)

        # Test overlapping sprints (and loading sprints from a file).
        with patch.object(Project, 'export_key', new=Path('test/sample')):
            sprints = Sprint_Data(Project('TEST'))

        self.assertEqual(sprints.find_sprint(datetime(2024, 3, 5, 6, 7, 8)), 93)
        self.assertEqual(sprints.find_sprint(datetime(2024, 3, 18, 12, 6, 0)),
                         94)
        self.assertEqual(sprints.find_sprint(datetime(2024, 3, 25, 11, 0, 0)),
                         93)
        self.assertEqual(sprints.find_sprint(datetime(2024, 4, 9, 10, 11, 12)),
                         96)

        # Test filtering on which sprints to consider.
        self.assertEqual(sprints.find_sprint(datetime(2024, 3, 19, 10, 0, 0),
                                             sprint_ids=(91, 92, 93, 95, 96)),
                         93)
        self.assertIsNone(sprints.find_sprint(datetime(2024, 3, 25, 11, 0, 0),
                                              sprint_ids=(91, 92, 94, 95, 96)))

class DatetimeTest(unittest.TestCase):
    """
    Tests for date and time functions.
    """

    def test_get_datetime(self) -> None:
        """
        Test converting a date string to an object without a timezone.
        """

        self.assertEqual(get_datetime('2024-04-17 15:10:05'),
                         datetime(2024, 4, 17, 15, 10, 5))

    def test_get_local_datetime(self) -> None:
        """
        Test converting a date string to an object with the local timezone.
        """

        self.assertEqual(get_local_datetime('2024-04-17 15:10:05'),
                         datetime(2024, 4, 17, 15, 10, 5,
                                  tzinfo=dateutil.tz.tzlocal()))

    def test_convert_local_datetime(self) -> None:
        """
        Test converting a datetime object to one in the local timezone.
        """

        self.assertEqual(convert_local_datetime(datetime(2024, 4, 17, 15, 10, 5)),
                         datetime(2024, 4, 17, 15, 10, 5,
                                  tzinfo=dateutil.tz.tzlocal()))

    def test_convert_utc_datetime(self) -> None:
        """
        Test converting a datetime object to one in the UTC timezone.
        """

        self.assertEqual(convert_utc_datetime(datetime(2024, 4, 17, 15, 10, 5,
                                                       tzinfo=timezone.utc)),
                         datetime(2024, 4, 17, 15, 10, 5,
                                  tzinfo=dateutil.tz.tzutc()))

    def test_format_date(self) -> None:
        """
        Test formatting a datetime object.
        """

        self.assertEqual(format_date(datetime(2024, 4, 17, 15, 10, 5)),
                         '2024-04-17 15:10:05')

    def test_parse_utc_date(self) -> None:
        """
        Test converting an ISO8601 date string.
        """

        date = datetime(2024, 4, 17, 15, 10, 5,
                        tzinfo=timezone.utc).astimezone(dateutil.tz.tzlocal())
        self.assertEqual(parse_utc_date('2024-04-17T15:10:05Z'),
                         date.strftime('%Y-%m-%d %H:%M:%S'))

    def test_parse_date(self) -> None:
        """
        Test converting a date string.
        """

        self.assertEqual(parse_date('2024-04-17T15:10:05.1234+00:00'),
                         '2024-04-17 15:10:05')
        self.assertEqual(parse_date('invalid date'), '1900-01-01 00:00:00')

class TextTest(unittest.TestCase):
    """
    Tests for text functions.
    """

    def test_parse_unicode(self) -> None:
        """
        Test converting unicode to a string without invalid characters.
        """

        self.assertEqual(parse_unicode('foo\ud800bar'), 'foo?bar')
