"""
Tests for implementation of connection to a MonetDB database.

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

from typing import Dict, List, Optional
import unittest
from unittest.mock import patch
from gatherer.database import Database

class DatabaseTest(unittest.TestCase):
    """
    Tests for database query utilities.
    """

    def setUp(self) -> None:
        patcher = patch('pymonetdb.connect', autospec=True)
        connector = patcher.start()
        self.addCleanup(patcher.stop)
        self.database = Database()
        self.connection = connector.return_value
        self.cursor = self.connection.cursor.return_value

    def test_close(self) -> None:
        """
        Test closing the database connection.
        """

        self.database.close()
        self.connection.close.assert_called_once_with()
        self.cursor.close.assert_called_once_with()

        # Closing an already closed connection does nothing.
        self.database.close()
        self.connection.close.assert_called_once_with()
        self.cursor.close.assert_called_once_with()

    def test_get_project_id(self) -> None:
        """
        Test retrieving the project ID from the database.
        """

        attrs: Dict[str, Optional[List[str]]] = {
            'fetchone.return_value': ['99']
        }
        self.cursor.configure_mock(**attrs)
        self.assertEqual(self.database.get_project_id('TEST'), 99)
        self.cursor.execute.assert_called_once()
        self.assertEqual(self.cursor.execute.call_args.kwargs['parameters'],
                         ['TEST'])

        attrs = {'fetchone.return_value': None}
        self.cursor.configure_mock(**attrs)
        self.assertIsNone(self.database.get_project_id('MISSING'))

    def test_set_project_id(self) -> None:
        """
        Test adding the project to the database.
        """

        attrs: Dict[str, Optional[List[str]]] = {
            'fetchone.return_value': ['99']
        }
        self.cursor.configure_mock(**attrs)
        self.assertEqual(self.database.set_project_id('TEST'), 99)

        # A problem with the database causes an error to be raised.
        attrs = {'fetchone.return_value': None}
        self.cursor.configure_mock(**attrs)
        with self.assertRaises(RuntimeError):
            self.database.set_project_id('FAIL')

    def test_execute(self) -> None:
        """
        Test performing a selection or update query.
        """

        self.assertIsNotNone(self.database.execute('SELECT 1', [], one=True))
        self.cursor.fetchone.assert_called_once_with()

        self.assertIsNotNone(self.database.execute('''SELECT * FROM gros.sprint
                                                      WHERE project_id = %s''',
                                                   [99]))
        self.cursor.fetchall.assert_called_once_with()

        self.assertIsNone(self.database.execute('''UPDATE gros.project
                                                   SET project_id = %s
                                                   WHERE name = %s''',
                                                [99, 'TEST'], update=True))
        self.connection.commit.assert_called_once_with()

    def test_execute_many(self) -> None:
        """
        Test executing a prepared query for sequences of parameters.
        """

        self.database.execute_many('INSERT INTO gros.project(name) VALUES(%s)',
                                   [['TEST'], ['TEST2']])
        self.connection.commit.assert_called_once_with()
