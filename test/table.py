"""
Tests for table structures.

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

from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union
import unittest
from unittest.mock import patch, MagicMock
from gatherer.table import PathLike, Table, Key_Table, Link_Table

class TableTest(unittest.TestCase):
    """
    Tests for data storage for eventual JSON output.
    """

    def _construct_path(self, path: PathLike, *args: str) -> Union[Path, MagicMock]:
        if path == 'secrets.json':
            return Path('test/sample/secrets.json')

        mock = MagicMock(spec_set=Path, name='Path')(path, *args)
        if path == 'missing':
            attrs = {'exists.return_value': False}
            mock.configure_mock(**attrs)

        self.path_mocks.setdefault((str(path),) + args, mock)
        return self.path_mocks[(str(path),) + args]

    def _build_table(self, name: str, filename: Optional[str] = None,
                     merge_update: bool = False,
                     encrypt_fields: Optional[Sequence[str]] = None) -> Table:
        return Table(name, filename=filename, merge_update=merge_update,
                     encrypt_fields=encrypt_fields)

    def setUp(self) -> None:
        self.path_mocks: Dict[Tuple[str, ...], MagicMock] = {}
        patcher = patch('gatherer.table.Path')
        self.path = patcher.start()
        self.path.configure_mock(side_effect=self._construct_path)
        self.addCleanup(patcher.stop)

        self.table = self._build_table('test',
                                       encrypt_fields=('username', 'email'))

    def test_name(self) -> None:
        """
        Test retrieving the name of the table.
        """

        self.assertEqual(self.table.name, 'test')

    def test_filename(self) -> None:
        """
        Test retrieving the filename of the table.
        """

        self.assertEqual(self.table.filename, 'data_test.json')

        table = self._build_table('issue', filename='data.json')
        self.assertEqual(table.filename, 'data.json')

    def test_get(self) -> None:
        """
        Test retrieving a copy of the table data.
        """

        self.assertEqual(self.table.get(), [])
        self.table.append({"username": "testuser"})
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()), {"username", "encrypted"})

    def test_has(self) -> None:
        """
        Test checking whether a row already exists within the table.
        """

        self.assertFalse(self.table.has({"foo": "bar"}))
        self.table.append({"username": "testuser"})
        self.assertTrue(self.table.has({"username": "testuser"}))

    def test_get_row(self) -> None:
        """
        Test retrieving a row from the table.
        """

        self.assertIsNone(self.table.get_row({"foo": "bar"}))
        self.table.append({"username": "testuser"})
        row = self.table.get_row({"username": "testuser"})
        if row is None: # pragma: no cover
            self.fail("Row was not retrieved")

        self.assertEqual(set(row.keys()), {"username", "encrypted"})
        self.assertEqual(row["encrypted"], "1")

        table = self._build_table('foo')
        table.append({"foo": "bar"})
        self.assertEqual(table.get_row({"foo": "bar"}), {"foo": "bar"})

    def test_append(self) -> None:
        """
        Test inserting a row into the table.
        """

        row = self.table.append({"username": "testuser", "email": "0"})
        if row is None: # pragma: no cover
            self.fail("Row was not appended")

        self.assertEqual(set(row.keys()), {"username", "email", "encrypted"})
        self.assertEqual(row["email"], "0")
        self.assertEqual(row["encrypted"], "1")

        # Already encrypted rows are not encrypted additionally when appended.
        rower = self.table.append({"username": "abcdef12345", "encrypted": "1"})
        if rower is None: # pragma: no cover
            self.fail("Row was not appended")

        self.assertEqual(rower, {"username": "abcdef12345", "encrypted": "1"})

        # If no encryption tokens are available in the table, then the appended
        # row is not encrypted.
        self.path.configure_mock(side_effect=None)
        attrs = {'exists.return_value': False}
        self.path.return_value.configure_mock(**attrs)
        table = self._build_table('test', encrypt_fields=('username', 'email'))
        rowest = table.append({"username": "testuser", "email": "foo@bar.test"})
        self.assertEqual(rowest, {
            "username": "testuser", "email": "foo@bar.test", "encrypted": "0"
        })

    def test_extend(self) -> None:
        """
        Test inserting multiple rows at once into the table.
        """

        rows = self.table.extend([
            {"username": "testuser"},
            {"username": "git"}
        ])
        for row in rows:
            if row is None: # pragma: no cover
                self.fail("Row was not extended")

            self.assertEqual(set(row.keys()), {"username", "encrypted"})
            self.assertEqual(row["encrypted"], "1")

    def test_update(self) -> None:
        """
        Test searching for a row and updating the fields.
        """

        self.table.append({"username": "git@domain.test", "email": "", "a": ""})
        self.table.update({"username": "git@domain.test", "email": "", "a": ""},
                          {"email": "git@domain.test", "a": "extra"})
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()),
                         {"username", "email", "a", "encrypted"})
        self.assertEqual(rows[0]["a"], "extra")
        self.assertEqual(rows[0]["encrypted"], "1")
        # Updated data is also encrypted.
        self.assertNotEqual(rows[0]["email"], "git@domain.test")

        # Also possible to search with adjusted usernames
        self.table.append({"username": "AD\\User", "email": "", "a": "info"})
        self.table.update({"username": "user", "email": "", "a": "info"},
                          {"email": "user@ad.test", "a": "new"})
        self.assertIsNotNone(self.table.get_row({
            "username": "user", "email": "user@ad.test", "a": "new"
        }))

    @patch('json.dump')
    @patch('json.load')
    def test_write(self, loader: MagicMock, dumper: MagicMock) -> None:
        """
        Test exporting the table data into a file.
        """

        self.table.write('test/sample')
        args = ('test/sample', 'data_test.json')
        self.assertIn(args, self.path_mocks)
        self.path_mocks[args].open.assert_called_once_with('w', encoding='utf-8')
        file = self.path_mocks[args].open.return_value.__enter__.return_value
        dumper.assert_called_once_with([], file, indent=4)

        dumper.reset_mock()
        loader.configure_mock(return_value=[{
            "issue_id": "10", "changelog_id": "2", "type": "bug"
        }])

        table = self._build_table('issue', filename='data.json',
                                  merge_update=True)
        table.append({"issue_id": "123", "changelog_id": "1", "type": "story"})
        table.write('test/sample/nest')
        args = ('test/sample/nest', 'data.json')
        self.assertIn(args, self.path_mocks)
        self.path_mocks[args].open.assert_called_with('w', encoding='utf-8')
        file = self.path_mocks[args].open.return_value.__enter__.return_value
        dumper.assert_called_once_with([
            {
                "issue_id": "123",
                "changelog_id": "1",
                "type": "story"
            },
            {
                "issue_id": "10",
                "changelog_id": "2",
                "type": "bug"
            }
        ], file, indent=4)

    @patch('json.load')
    def test_load(self, loader: MagicMock) -> None:
        """
        Test loading the table data from the exported file.
        """

        loader.configure_mock(return_value=[{"username": "testuser"}])
        self.table.load('test/sample')
        args = ('test/sample', 'data_test.json')
        self.assertIn(args, self.path_mocks)
        self.path_mocks[args].open.assert_called_once_with('r', encoding='utf-8')
        file = self.path_mocks[args].open.return_value.__enter__.return_value
        loader.assert_called_once_with(file)

        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()), {"username", "encrypted"})

        # Nonexistent file paths lead to no additional file reading.
        self.table.load('missing')
        self.path_mocks[('missing', 'data_test.json')].open.assert_not_called()
        self.assertEqual(len(self.table.get()), 1)

    def test_clear(self) -> None:
        """
        Test removing all rows from the table.
        """

        self.table.append({"username": "testuser"})
        self.table.clear()
        self.assertEqual(self.table.get(), [])

    def test_collection(self) -> None:
        """
        Test collection methods.
        """

        self.table.append({"username": "testuser"})
        self.assertTrue({"username": "testuser"} in self.table)
        self.assertFalse("testuser" in self.table)

        count = 0
        for row in iter(self.table):
            self.assertEqual(set(row.keys()), {"username", "encrypted"})
            count += 1
        self.assertEqual(count, 1)

        self.assertEqual(len(self.table), 1)

class KeyTableTest(TableTest):
    """
    Tests for data storage of a table that has a primary, unique key.
    """

    def _build_table(self, name: str, filename: Optional[str] = None,
                     merge_update: bool = False,
                     encrypt_fields: Optional[Sequence[str]] = None) -> Table:
        key_map = {
            'test': 'username',
            'issue': 'issue_id'
        }
        return Key_Table(name, key_map.get(name, name),
                         filename=filename, merge_update=merge_update,
                         encrypt_fields=encrypt_fields)

    def test_append_key(self) -> None:
        """
        Test appending rows to the key table.
        """

        self.assertIsNotNone(self.table.append({"username": "testuser"}))
        self.assertIsNone(self.table.append({"username": "testuser"}))
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0])

    def test_update_key(self) -> None:
        """
        Test updating rows to the key table.
        """

        self.table.append({"username": "git@domain.test", "email": "", "a": ""})
        # Only need to provide the key in the search row.
        self.table.update({"username": "git@domain.test"},
                          {"email": "git@domain.test", "a": "extra"})
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()),
                         {"username", "email", "a", "encrypted"})
        self.assertEqual(rows[0]["a"], "extra")
        self.assertEqual(rows[0]["encrypted"], "1")
        # Updated data is also encrypted.
        self.assertNotEqual(rows[0]["email"], "git@domain.test")

        with self.assertRaises(ValueError):
            # Cannot change the key to another value.
            self.table.update({"username": "git@domain.test"},
                              {"username": "git", "a": "new"})

    def test_subscription(self) -> None:
        """
        Test subscription methods of the key table.
        """

        if not isinstance(self.table, Key_Table): # pragma: no cover
            self.fail("Incorrect table")

        self.table.append({"username": "testuser", "a": "extra"})
        row = self.table["testuser"]
        self.assertEqual(set(row.keys()), {"username", "a", "encrypted"})
        self.assertEqual(row["a"], "extra")
        self.assertEqual(row["encrypted"], "1")

        with self.assertRaises(TypeError):
            self.assertNotEqual(self.table[0], row)

        self.table["testuser"] = {"email": "user@server.test", "a": "new"}
        row = self.table["testuser"]
        self.assertEqual(set(row.keys()),
                         {"username", "email", "a", "encrypted"})
        self.assertEqual(row["a"], "new")
        self.assertEqual(row["encrypted"], "1")
        # Updated data is also encrypted.
        self.assertNotEqual(row["email"], "user@server.test")

        # Assignment also allows adding new tables.
        self.table["user2"] = {"a": "second"}
        self.assertEqual(len(self.table), 2)
        row = self.table["user2"]
        self.assertEqual(set(row.keys()), {"username", "a", "encrypted"})
        self.assertEqual(row["a"], "second")
        self.assertEqual(row["encrypted"], "1")

        with self.assertRaises(TypeError):
            self.table[3] = {"email": "foo@bar.test"}
        with self.assertRaises(TypeError):
            self.table["user3"] = "bar@baz.test"

class LinkTableTest(TableTest):
    """
    Tests for data storage of a table that has a combination of columns that
    make up a primary key.
    """

    def _build_table(self, name: str, filename: Optional[str] = None,
                     merge_update: bool = False,
                     encrypt_fields: Optional[Sequence[str]] = None) -> Table:
        key_map = {
            'test': ('username',),
            'issue': ('issue_id', 'changelog_id')
        }
        return Link_Table(name, key_map.get(name, (name,)),
                          filename=filename, merge_update=merge_update,
                          encrypt_fields=encrypt_fields)

    def test_append_link(self) -> None:
        """
        Test appending rows to the link table.
        """

        self.assertIsNotNone(self.table.append({"username": "testuser"}))
        self.assertIsNone(self.table.append({"username": "testuser"}))
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0])

    def test_update_link(self) -> None:
        """
        Test updating rows to the link table.
        """

        self.table.append({"username": "git@domain.test", "email": "", "a": ""})
        # Only need to provide the link keys in the search row.
        self.table.update({"username": "git@domain.test"},
                          {"email": "git@domain.test", "a": "extra"})
        rows = self.table.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()),
                         {"username", "email", "a", "encrypted"})
        self.assertEqual(rows[0]["a"], "extra")
        self.assertEqual(rows[0]["encrypted"], "1")
        # Updated data is also encrypted.
        self.assertNotEqual(rows[0]["email"], "git@domain.test")

        with self.assertRaises(ValueError):
            # Cannot change the key to another value.
            self.table.update({"username": "git@domain.test"},
                              {"username": "git", "a": "new"})

    def test_subscription(self) -> None:
        """
        Test subscription methods of the link table.
        """

        if not isinstance(self.table, Link_Table): # pragma: no cover
            self.fail("Incorrect table")

        self.table.append({"username": "testuser", "a": "extra"})
        row = self.table[("testuser",)]
        self.assertEqual(set(row.keys()), {"username", "a", "encrypted"})
        self.assertEqual(row["a"], "extra")
        self.assertEqual(row["encrypted"], "1")

        with self.assertRaises(TypeError):
            self.assertNotEqual(self.table["testuser"], row)

        self.table[("testuser",)] = {"email": "user@server.test", "a": "new"}
        row = self.table[("testuser",)]
        self.assertEqual(set(row.keys()),
                         {"username", "email", "a", "encrypted"})
        self.assertEqual(row["a"], "new")
        self.assertEqual(row["encrypted"], "1")
        # Updated data is also encrypted.
        self.assertNotEqual(row["email"], "user@server.test")

        # Assignment also allows adding new tables.
        self.table[("user2",)] = {"a": "second"}
        self.assertEqual(len(self.table), 2)
        row = self.table[("user2",)]
        self.assertEqual(set(row.keys()), {"username", "a", "encrypted"})
        self.assertEqual(row["a"], "second")
        self.assertEqual(row["encrypted"], "1")

        with self.assertRaises(TypeError):
            self.table["user3"] = {"email": "foo@bar.test"}
        with self.assertRaises(TypeError):
            self.table[("user3",)] = "bar@baz.test"
        with self.assertRaises(ValueError):
            self.table[("user3", "more")] = {"email": "baz@qux.test"}
