"""
Tests for module that synchronizes update tracker files.

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
from subprocess import CalledProcessError
from typing import Dict, List, Optional, Union
import unittest
from unittest.mock import patch, Mock, MagicMock
from gatherer.domain.project import Project
from gatherer.update import Update_Tracker, Database_Tracker, SSH_Tracker

DatabaseParams = List[Union[str, datetime]]

class UpdateTrackerTest(unittest.TestCase):
    """
    Tests for abstract source with update tracker files.
    """

    @patch('gatherer.update.Path', autospec=True)
    @patch('os.utime')
    def test_update_file(self, utime: MagicMock, path: MagicMock) -> None:
        """
        Test checking whether an update tracker file from a remote source is
        updated more recently than a local version.
        """

        tracker = Update_Tracker(Project('TEST'))

        attrs: Dict[str, Union[bool, Mock]] = {'exists.return_value': False}
        path.return_value.configure_mock(**attrs)

        # No local file, so needs an update.
        tracker.update_file('test-update.txt', '12345',
                            datetime(2024, 4, 15, 3, 0, 0, tzinfo=timezone.utc))
        path.return_value.exists.assert_called_once_with()
        path.return_value.open.assert_called_once_with('w', encoding='utf-8')
        file = path.return_value.open.return_value.__enter__.return_value
        file.write.assert_called_once_with('12345')
        utime.assert_called_once()
        self.assertEqual(utime.call_args.args[0],
                         path('export/TEST/test-update.txt'))
        self.assertEqual(utime.call_args.args[1][1], 1713150000)

        path.return_value.reset_mock()
        utime.reset_mock()

        attrs = {
            'exists.return_value': True,
            'stat.return_value': Mock(st_mtime=1713151317)
        }
        path.return_value.configure_mock(**attrs)

        # Already up to date.
        tracker.update_file('test-update.txt', '67890',
                            datetime(2024, 4, 14, tzinfo=timezone.utc))
        path.return_value.exists.assert_called_once_with()
        path.return_value.open.assert_not_called()
        utime.assert_not_called()

        path.return_value.reset_mock()

        # Updating file from remote tracker file.
        tracker.update_file('test-update.txt', '67890',
                            datetime(2024, 4, 15, 8, 55, 17,
                                     tzinfo=timezone.utc))
        path.return_value.exists.assert_called_once_with()
        path.return_value.open.assert_called_once_with('w', encoding='utf-8')
        file = path.return_value.open.return_value.__enter__.return_value
        file.write.assert_called_once_with('67890')
        utime.assert_called_once()
        self.assertEqual(utime.call_args.args[0],
                         path('export/TEST/test-update.txt'))
        self.assertEqual(utime.call_args.args[1][1], 1713171317)

class DatabaseTrackerTest(unittest.TestCase):
    """
    Tests for database source with update tracker files.
    """

    def setUp(self) -> None:
        project_patcher = patch.object(Project, 'make_export_directory')
        self.make_export_directory = project_patcher.start()
        self.addCleanup(project_patcher.stop)

        self.project = Project('TEST')

        tracker_patcher = patch.object(Update_Tracker, 'update_file')
        self.update_file = tracker_patcher.start()
        self.addCleanup(tracker_patcher.stop)

        self.tracker = Database_Tracker(self.project, database='gros_test')

    @patch('gatherer.update.Database', autospec=True)
    def test_retrieve(self, database: MagicMock) -> None:
        """
        Test retrieving the update tracker files.
        """

        params: DatabaseParams = [
            'test-update.txt', '12345', datetime(2024, 4, 16)
        ]
        attrs: Dict[str, Optional[Union[int, List[DatabaseParams]]]] = {
            'get_project_id.return_value': 99,
            'execute.return_value': [params]
        }
        connection = database.return_value.__enter__.return_value
        connection.configure_mock(**attrs)

        # Retrieve any update trackers.
        self.tracker.retrieve()
        self.make_export_directory.assert_called_once_with()
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'], [99])
        self.update_file.assert_called_once_with(*params)

        connection.reset_mock()
        self.update_file.reset_mock()

        # Retrieve specific update trackers.
        self.tracker.retrieve(files=['test-update.txt'])
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'],
                         [99, 'test-update.txt'])
        self.update_file.assert_called_once_with(*params)

        connection.reset_mock()
        self.update_file.reset_mock()

        # Retrieve update trackers from unknown project.
        attrs = {'get_project_id.return_value': None}
        connection.configure_mock(**attrs)
        self.tracker.retrieve()
        connection.execute.assert_not_called()

        # Retrieve trackers that are not found.
        attrs = {
            'get_project_id.return_value': 99,
            'execute.return_value': None
        }
        connection.configure_mock(**attrs)
        self.tracker.retrieve(files=('missing.txt', 'invalid.log'))
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'],
                         [99, 'missing.txt', 'invalid.log'])
        self.update_file.assert_not_called()

    @patch('gatherer.update.Database', autospec=True)
    def test_retrieve_content(self, database: MagicMock) -> None:
        """
        Test retrieving the contents of a single update tracker file.
        """

        attrs: Dict[str, Optional[Union[int, List[str]]]] = {
            'get_project_id.return_value': 99,
            'execute.return_value': ['67890']
        }
        connection = database.return_value.__enter__.return_value
        connection.configure_mock(**attrs)

        self.assertEqual(self.tracker.retrieve_content('test-update.txt'),
                         '67890')
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'],
                         [99, 'test-update.txt'])

        connection.reset_mock()

        # Retrieve tracker from unknown project.
        attrs = {'get_project_id.return_value': None}
        connection.configure_mock(**attrs)
        self.assertIsNone(self.tracker.retrieve_content('test-update.txt'))
        connection.execute.assert_not_called()

        # Retrieve tracker that is not found.
        attrs = {
            'get_project_id.return_value': 99,
            'execute.return_value': None
        }
        connection.configure_mock(**attrs)
        self.assertIsNone(self.tracker.retrieve_content('missing.txt'))
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'],
                         [99, 'missing.txt'])

    @patch('gatherer.update.Database', autospec=True)
    def test_put_content(self, database: MagicMock) -> None:
        """
        Test updating the remote update tracker file.
        """

        attrs: Dict[str, Optional[int]] = {'get_project_id.return_value': 99}
        connection = database.return_value.__enter__.return_value
        connection.configure_mock(**attrs)

        self.tracker.put_content('test-update.txt', '12345')
        connection.execute.assert_called_once()
        self.assertEqual(connection.execute.call_args.kwargs['parameters'],
                         ['12345', 99, 'test-update.txt'])

        connection.reset_mock()

        # Update tracker at unknown project.
        attrs = {'get_project_id.return_value': None}
        connection.configure_mock(**attrs)
        self.tracker.put_content('test-update.txt', '12345')
        connection.execute.assert_not_called()

class SSHTrackerTest(unittest.TestCase):
    """
    Tests for external server connection with SSH public key authentication and
    a home directory containing update tracker files.
    """

    def setUp(self) -> None:
        project_patcher = patch.object(Project, 'make_export_directory')
        self.make_export_directory = project_patcher.start()
        self.addCleanup(project_patcher.stop)

        self.project = Project('TEST')

        tracker_patcher = patch.object(Update_Tracker, 'update_file')
        self.update_file = tracker_patcher.start()
        self.addCleanup(tracker_patcher.stop)

        self.tracker = SSH_Tracker(self.project, user='agent-test',
                                   host='controller.test')

    def test_remote_path(self) -> None:
        """
        Test retrieving the remote path of the SSH server.
        """

        self.assertEqual(self.tracker.remote_path,
                         'agent-test@controller.test:~/update/TEST')

    @patch('subprocess.check_output')
    def test_retrieve(self, process: MagicMock) -> None:
        """
        Test retrieving the update tracker files.
        """

        # Files are required to determine which ones to retrieve
        self.tracker.retrieve()
        self.make_export_directory.assert_called_once_with()
        process.assert_not_called()

        process.configure_mock(return_value=b'Welcome to controller host')
        self.tracker.retrieve(files=['test-update.txt'])
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][-2:], [
            'agent-test@controller.test:~/update/TEST/\\{test-update.txt\\}',
            'export/TEST'
        ])

        process.reset_mock()

        # Spurious errors are reported.
        error = b'Could not connect to host controller.test: No such name'
        process.configure_mock(side_effect=CalledProcessError(1, '',
                                                              output=error))
        with self.assertRaises(RuntimeError):
            self.tracker.retrieve(files=['test-update.txt'])

        # Missing files are ignored.
        error = b'No such file or directory: missing.txt'
        process.configure_mock(side_effect=CalledProcessError(1, '',
                                                          output=error))
        self.tracker.retrieve(files=('missing.txt', 'oops'))
        self.assertEqual(process.call_args.args[0][-2:], [
            'agent-test@controller.test:~/update/TEST/\\{missing.txt,oops\\}',
            'export/TEST'
        ])

    @patch('subprocess.check_output')
    def test_retrieve_content(self, process: MagicMock) -> None:
        """
        Test retrieving the contents of a single update tracker file.
        """

        process.configure_mock(return_value=b'67890')
        self.assertEqual(self.tracker.retrieve_content('test-update.txt'),
                         '67890')
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][-2],
                         'agent-test@controller.test:~/update/TEST/test-update.txt')

        process.reset_mock()

        # Retrieve a missing file.
        process.configure_mock(side_effect=CalledProcessError(1, ''))
        self.assertIsNone(self.tracker.retrieve_content('missing.txt'))
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][-2],
                         'agent-test@controller.test:~/update/TEST/missing.txt')

    @patch('tempfile.NamedTemporaryFile', autospec=True)
    @patch('subprocess.run')
    def test_put_content(self, process: MagicMock, tempfile: MagicMock) -> None:
        """
        Test updating the remote update tracker file.
        """

        self.tracker.put_content('test-update.txt', '12345')
        tempfile.assert_called_once()
        file = tempfile.return_value.__enter__.return_value
        file.write.assert_called_once_with('12345')
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][-2:], [
            file.name,
            'agent-test@controller.test:~/update/TEST/test-update.txt'
        ])

        process.reset_mock()

        # Errors are ignored.
        process.configure_mock(side_effect=CalledProcessError(1, ''))
        self.tracker.put_content('invalid name', '-')
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][-2:], [
            file.name, 'agent-test@controller.test:~/update/TEST/invalid name'
        ])
