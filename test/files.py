"""
Tests for module that supports retrieving files from a data store.

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
from unittest.mock import patch, MagicMock, Mock
import owncloud
from gatherer.files import File_Store, PathExistenceError

@File_Store.register('test')
class Test_Store(File_Store): # pragma: no cover
    """
    File store with no backend.
    """

    def login(self, username: str, password: str) -> None:
        pass

    def get_file(self, remote_file: str, local_file: str) -> None:
        pass

    def get_file_contents(self, remote_file: str) -> str:
        return ''

    def get_directory(self, remote_path: str, local_path: str) -> None:
        pass

    def put_file(self, local_file: str, remote_file: str) -> None:
        pass

    def put_directory(self, local_path: str, remote_path: str) -> None:
        pass

class FileStoreTest(unittest.TestCase):
    """
    Tests for file store.
    """

    def test_get_type(self) -> None:
        """
        Test retrieving a class registered for a store type.
        """

        self.assertEqual(File_Store.get_type('test'), Test_Store)
        with self.assertRaises(RuntimeError):
            File_Store.get_type('nonexistent-type')

class OwnCloudStoreTest(unittest.TestCase):
    """
    Tests for file store using an ownCloud backend.
    """

    def setUp(self) -> None:
        patcher = patch('owncloud.Client')
        self.client = patcher.start().return_value
        self.addCleanup(patcher.stop)

        store = File_Store.get_type('owncloud')
        self.store = store('http://owncloud.test')

    def test_login(self) -> None:
        """
        Test logging in to the store.
        """

        self.store.login('ocuser', 'ocpass')
        self.client.login.assert_called_once_with('ocuser', 'ocpass')

    def test_get_file(self) -> None:
        """
        Test retrieving a file.
        """

        self.store.get_file('remote/file', 'test/sample/owncloud.tmp')
        self.client.get_file.assert_called_once_with('remote/file',
                                                     'test/sample/owncloud.tmp')

        attrs = {'get_file.side_effect': owncloud.HTTPResponseError(404)}
        self.client.configure_mock(**attrs)
        with self.assertRaises(PathExistenceError):
            self.store.get_file('missing/file', 'test/sample/ownloud.tmp')

        error = owncloud.HTTPResponseError(Mock(status_code=500,
                                                content='connection error'))
        attrs = {'get_file.side_effect': error}
        self.client.configure_mock(**attrs)
        with self.assertRaisesRegex(RuntimeError, 'connection error'):
            self.store.get_file('connection/error', 'test/sample/ownloud.tmp')


    def test_get_file_contents(self) -> None:
        """
        Test retrieving the file contents from a remote path without storing it.
        """

        attrs = {'get_file_contents.return_value': 'bla'}
        self.client.configure_mock(**attrs)
        self.assertEqual(self.store.get_file_contents('remote/file'), 'bla')
        self.client.get_file_contents.assert_called_once_with('remote/file')

    @patch('gatherer.files.tempfile', autospec=True)
    @patch('gatherer.files.shutil', autospec=True)
    @patch('gatherer.files.ZipFile', autospec=True)
    def test_get_directory(self, zip_file: MagicMock, shutil: MagicMock,
                           tempfile: MagicMock) -> None:
        """
        Test retrieving all files in the directory at the remote path.
        """

        tmp_attrs = {'mkdtemp.return_value': 'test/sample/tmpdir'}
        tempfile.configure_mock(**tmp_attrs)

        self.store.get_directory('remote/path', 'test/sample/local')
        self.client.get_directory_as_zip.assert_called_once()
        self.assertEqual(self.client.get_directory_as_zip.call_args.args[0],
                         'remote/path')
        zip_file.assert_called_once()
        shutil.move.assert_called_once()
        self.assertEqual(shutil.move.call_args.args[1], 'test/sample/local')

        attrs = {
            'get_directory_as_zip.side_effect': owncloud.HTTPResponseError(404)
        }
        self.client.configure_mock(**attrs)
        with self.assertRaises(PathExistenceError):
            self.store.get_directory('remote/nonexistent', 'test/sample/new')

        error = owncloud.HTTPResponseError(Mock(status_code=500,
                                                content='connection error'))
        attrs = {'get_directory_as_zip.side_effect': error}
        self.client.configure_mock(**attrs)
        with self.assertRaisesRegex(RuntimeError, 'connection error'):
            self.store.get_directory('connect/error', 'test/sample/path')

    def test_put_file(self) -> None:
        """
        Test uploading the contents of the file from a local path to the store.
        """

        self.store.put_file('test/sample/owncloud.log', 'remote/data.txt')
        self.client.put_file.assert_called_once_with('remote/data.txt',
                                                     'test/sample/owncloud.log')

    def test_put_directory(self) -> None:
        """
        Test uploading an entire directory and all its subdirectories and files
        in them from a local path to the store.
        """

        self.store.put_directory('test/sample', 'remote/nested/path')
        self.client.put_directory.assert_called_once_with('remote/nested/path',
                                                          'test/sample')
