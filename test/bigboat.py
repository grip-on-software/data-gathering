"""
Tests for BigBoat API utilities.

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

import json
import unittest
from unittest.mock import patch, MagicMock
from gatherer.bigboat import Statuses, StatusesIter, StatusesSequence
from gatherer.domain.project import Project
from gatherer.utils import convert_local_datetime, format_date, get_utc_datetime

class StatusesTest(unittest.TestCase):
    """
    Tests for conversion of BigBoat status items to event records suitable for
    MonetDB.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')

    def test_from_api(self) -> None:
        """
        Test the conversion from API result list into Statuses object.
        """

        with open('test/sample/bigboat_api_status.json', 'r',
                  encoding='utf-8') as api_file:
            status: StatusesIter = json.load(api_file)
        statuses = Statuses.from_api(self.project, status)
        with open('test/sample/bigboat_api_data.json', 'r',
                  encoding='utf-8') as data_file:
            self.assertEqual(statuses.export(), json.load(data_file))

    @patch('gatherer.bigboat.Database', autospec=True)
    def test_database(self, database: MagicMock) -> None:
        """
        Test the `database` property.
        """

        statuses = Statuses(self.project, database='gros_test')
        self.assertEqual(statuses.database, database.return_value)
        database.assert_called_once_with(database='gros_test')

        database.configure_mock(side_effect=EnvironmentError)
        problem = Statuses(self.project)
        self.assertIsNone(problem.database)
        database.reset_mock(side_effect=True)

    @patch('gatherer.bigboat.Database', autospec=True)
    def test_project_id(self, database: MagicMock) -> None:
        """
        Test the `project_id` property.
        """

        get_project_id = database.return_value.get_project_id
        statuses = Statuses(self.project)
        self.assertEqual(statuses.project_id, get_project_id.return_value)
        # Accessing the property multiple times does not cause extra queries.
        self.assertEqual(statuses.project_id, get_project_id.return_value)
        get_project_id.assert_called_once_with('TEST')

        # If the database is unavailable, then the statuses do not have access
        # to a project ID.
        database.configure_mock(side_effect=EnvironmentError)
        problem = Statuses(self.project)
        self.assertIsNone(problem.project_id)

    @patch('gatherer.bigboat.Database', autospec=True)
    def test_add_batch(self, database: MagicMock) -> None:
        """
        Test adding new statuses to a batch and optional update of the database.
        """

        with open('test/sample/data_bigboat.json', 'r', encoding='utf-8') as \
            statuses_file:
            data: StatusesSequence = json.load(statuses_file)

        statuses = Statuses(self.project)
        self.assertTrue(statuses.add_batch(data))
        # Export provides the data not yet imported into the database.
        self.assertEqual(statuses.export(), data)

        batch = database.return_value.execute_many
        with patch.object(Statuses, 'MAX_BATCH_SIZE', 2):
            attrs = {'get_project_id.return_value': 99}
            database.return_value.configure_mock(**attrs)
            self.assertTrue(statuses.add_batch(data))
            batch.assert_called_once()
            self.assertEqual(batch.call_args.args[1], [
                [
                    99, item['name'],
                    format_date(convert_local_datetime(get_utc_datetime(
                        item['checked_time']
                    ))),
                    item['ok'], item['value'], item['max']
                ]
                for item in data
            ])

            database.configure_mock(side_effect=EnvironmentError)
            problem = Statuses(self.project)
            # If the database is not available when we need to import, then the
            # new data becomes lost and the original data is left.
            self.assertTrue(problem.add_batch(data))
            self.assertFalse(problem.add_batch([data[0]]))
            self.assertEqual(problem.export(), data)

    @patch('gatherer.bigboat.Database', autospec=True)
    def test_update(self, database: MagicMock) -> None:
        """
        Test adding rows to the database, also for source information.
        """

        source = 'http://dashboard.test'
        statuses = Statuses(self.project, source=source)
        attrs = {
            'get_project_id.return_value': 99,
            'execute.return_value': None
        }
        database.return_value.configure_mock(**attrs)
        insert = database.return_value.execute
        # No data yet
        self.assertTrue(statuses.update())
        # The update calls to check and insert source information
        self.assertEqual(insert.call_count, 2)
        for call_args in insert.call_args_list:
            self.assertEqual(call_args.args[1], [99, 'bigboat', source, source])

        with open('test/sample/bigboat_api_status.json', 'r',
                  encoding='utf-8') as api_file:
            status: StatusesIter = json.load(api_file)
        api = Statuses.from_api(self.project, status)
        self.assertTrue(api.update())
        batch = database.return_value.execute_many
        batch.assert_called_once()

        with open('test/sample/bigboat_api_data.json', 'r',
                  encoding='utf-8') as data_file:
            data: StatusesSequence = json.load(data_file)

        self.assertEqual(batch.call_args.args[1], [
            [
                99, item['name'],
                format_date(convert_local_datetime(get_utc_datetime(
                    item['checked_time']
                ))),
                item['ok'], item['value'], item['max']
            ]
            for item in data
        ])

        # The data remains when update is called directly
        self.assertEqual(api.export(), data)

    def test_export(self) -> None:
        """
        Test retrieving the status records.
        """

        statuses = Statuses(self.project)
        with open('test/sample/data_bigboat.json', 'r', encoding='utf-8') as \
            statuses_file:
            data: StatusesIter = json.load(statuses_file)
            statuses.add_batch(data)

        self.assertEqual(statuses.export(), data)
