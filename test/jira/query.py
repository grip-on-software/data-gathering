"""
Tests for module that handles the JIRA API query.

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

import unittest
from unittest.mock import MagicMock
from gatherer.domain.project import Project
from gatherer.domain.source import Jira
from gatherer.jira.collector import Collector
from gatherer.jira.query import Query
from gatherer.jira.update import Update_Tracker

class QueryTest(unittest.TestCase):
    """
    Tests for object that handles the JIRA API query.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)
        self.source = MagicMock(spec=Jira)
        self.api = self.source.jira_api
        self.query = Query(self.jira, self.source)
        self.jql = 'project=TEST AND updated > "1900-01-01 01:01"'

    def test_properties(self) -> None:
        """
        Test properties of the query object.
        """

        self.assertEqual(self.query.query, self.jql)
        self.assertEqual(self.query.api, self.api)
        self.assertEqual(self.query.latest_update,
                         Update_Tracker.NULL_TIMESTAMP)
        self.assertEqual(self.query.iterator_limiter.skip, 0)

        custom = Query(self.jira, self.source, query='component=foobar')
        self.assertEqual(custom.query, f'{self.jql} AND (component=foobar)')

    def test_update(self) -> None:
        """
        Test updating the iteration tracker.
        """

        self.query.update()
        self.assertEqual(self.query.iterator_limiter.skip, 100)

    def test_perform_batched_query(self) -> None:
        """
        Test retrieving a batch of issue results.
        """

        result = self.query.perform_batched_query(True)
        self.assertEqual(result, self.api.search_issues.return_value)
        self.api.search_issues.assert_called_once()
        self.assertEqual(self.api.search_issues.call_args.args[0], self.jql)
        self.assertEqual(self.api.search_issues.call_args.kwargs['startAt'], 0)
        self.assertEqual(self.api.search_issues.call_args.kwargs['expand'],
                         'attachment,changelog')
        self.assertFalse(self.api.search_issues.call_args.kwargs['json_result'])
        latest_update = self.query.latest_update
        self.assertNotEqual(latest_update, Update_Tracker.NULL_TIMESTAMP)

        self.api.search_issues.reset_mock()
        self.assertEqual(self.query.perform_batched_query(False), [])
        self.api.search_issues.assert_not_called()
        self.assertEqual(self.query.latest_update, latest_update)
