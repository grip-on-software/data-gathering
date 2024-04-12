"""
Tests for module that securely stores and retrieves project-specific encryption.

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

from typing import Any, Dict, List
import unittest
from unittest.mock import patch, MagicMock
from gatherer.domain.project import Project
from gatherer.salt import Salt

class SaltTest(unittest.TestCase):
    """
    Tests for encryption salt storage.
    """

    @patch('hashlib.sha256')
    def test_encrypt(self, hasher: MagicMock) -> None:
        """
        Test encoding a value with salt and pepper.
        """

        Salt.encrypt(b'foo', b'bar', b'baz')
        hasher.assert_called_once_with(b'barfoobaz')
        hasher.return_value.hexdigest.assert_called_once_with()

    @patch('gatherer.salt.Database', autospec=True)
    def test_database(self, database: MagicMock) -> None:
        """
        Test retrieving the database connection.
        """

        salt = Salt(database='gros_test')
        self.assertEqual(salt.database, database.return_value)
        # Accessing the database multiple times does not open more connections.
        self.assertEqual(salt.database, database.return_value)
        database.assert_called_once_with(database='gros_test')

        database.configure_mock(side_effect=EnvironmentError)
        problem = Salt()
        self.assertIsNone(problem.database)
        database.reset_mock(side_effect=True)

    @patch('gatherer.salt.Database', autospec=True)
    def test_project_id(self, database: MagicMock) -> None:
        """
        Test retrieving the project ID.
        """

        get_project_id = database.return_value.get_project_id
        project = Project('TEST')
        salt = Salt(project)
        self.assertEqual(salt.project_id, get_project_id.return_value)
        # Accessing the property multiple times does not cause extra queries.
        self.assertEqual(salt.project_id, get_project_id.return_value)
        get_project_id.assert_called_once_with('TEST')

        # If the project did not exist, then a new ID is created.
        attrs = {
            'get_project_id.return_value': None,
            'set_project_id.return_value': 42
        }
        database.return_value.configure_mock(**attrs)
        create = Salt(project)
        self.assertEqual(create.project_id, 42)
        database.return_value.set_project_id.assert_called_once_with('TEST')

        # If the project is unavailable, then the ID is set to zero.
        zero = Salt()
        self.assertEqual(zero.project_id, 0)

    @patch('gatherer.salt.Database', autospec=True)
    def test_execute(self, database: MagicMock) -> None:
        """
        Test retrieving or generating and updating the project-specific salts.
        """

        attrs: Dict[str, Any] = {
            'get_project_id.return_value': 42,
            'execute.return_value': ['salt', 'pepper']
        }
        database.return_value.configure_mock(**attrs)
        execute = database.return_value.execute
        salt = Salt(Project('TEST'))
        self.assertEqual(salt.execute(), ('salt', 'pepper'))
        execute.assert_called_once()
        database.return_value.reset_mock()

        attrs = {
            'get_project_id.return_value': 42,
            'execute.return_value': None
        }
        database.return_value.configure_mock(**attrs)
        result = salt.execute()
        self.assertEqual(execute.call_count, 2)
        expected: List[Any] = [42]
        expected.extend(result)
        self.assertEqual(execute.call_args.kwargs['parameters'], expected)

    @patch('gatherer.salt.Database', autospec=True)
    def test_get(self, database: MagicMock) -> None:
        """
        Test retrieving the project-specific salts from the database.
        """

        attrs: Dict[str, Any] = {
            'get_project_id.return_value': 42,
            'execute.return_value': ['salt', 'pepper']
        }
        database.return_value.configure_mock(**attrs)
        execute = database.return_value.execute
        salt = Salt(Project('TEST'))
        self.assertEqual(salt.get(), ('salt', 'pepper'))
        execute.assert_called_once()
        self.assertEqual(execute.call_args.kwargs['parameters'], [42])
        database.return_value.reset_mock()

        # If the salts are not in the database, then a ValueError is raised.
        attrs = {
            'get_project_id.return_value': 42,
            'execute.return_value': None
        }
        database.return_value.configure_mock(**attrs)
        salt = Salt(Project('TEST'))
        with self.assertRaises(ValueError):
            salt.get()
        database.return_value.reset_mock()

        # If the database connection is missing, then a RuntimeError is raised.
        database.configure_mock(side_effect=EnvironmentError)
        problem = Salt()
        with self.assertRaises(RuntimeError):
            problem.get()
        database.reset_mock(side_effect=True)

    @patch('gatherer.salt.Database', autospec=True)
    def test_update(self, database: MagicMock) -> None:
        """
        Test generating and updating the project-specific salts.
        """

        attrs = {'get_project_id.return_value': 42}
        database.return_value.configure_mock(**attrs)
        execute = database.return_value.execute
        salt = Salt(Project('TEST'))
        result = salt.update()
        execute.assert_called_once()
        expected: List[Any] = [42]
        expected.extend(result)
        self.assertEqual(execute.call_args.kwargs['parameters'], expected)

        # If the database connection is missing, then a RuntimeError is raised.
        database.configure_mock(side_effect=EnvironmentError)
        problem = Salt()
        with self.assertRaises(RuntimeError):
            problem.update()
        database.reset_mock(side_effect=True)
