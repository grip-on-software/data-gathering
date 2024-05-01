"""
Tests for module that tracks latest update time.

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

from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch
from gatherer.domain.project import Project
from gatherer.jira.update import Updated_Time, Update_Tracker

class UpdatedTimeTest(unittest.TestCase):
    """
    Tests for tracker of the latest update time of issues.
    """

    def setUp(self) -> None:
        self.updated_time = Updated_Time('2024-04-24 20:44')

    def test_is_newer(self) -> None:
        """
        Test comparing timestamps against the update date.
        """

        self.assertTrue(self.updated_time.is_newer('2024-04-24 21:54:36'))
        self.assertFalse(self.updated_time.is_newer('2024-04-20 20:00:04'))

    def test_properties(self) -> None:
        """
        Test properties of the update time.
        """

        self.assertEqual(self.updated_time.timestamp, '2024-04-24 20:44')
        self.assertEqual(self.updated_time.date,
                         datetime(2024, 4, 24, 20, 44, 0))

class UpdateTrackerTest(unittest.TestCase):
    """
    Tests for storage of JIRA update time timestamp.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        patcher = patch('gatherer.jira.update.Path')
        self.path = patcher.start()

    def test_get_updated_since(self) -> None:
        """
        Test retrieving the latest update timestamp.
        """

        loaded_update_tracker = Update_Tracker(self.project, '2024-04-24 16:00')
        self.path.assert_called_with(Path('export/TEST'), 'jira-updated.txt')
        self.assertEqual(loaded_update_tracker.get_updated_since(),
                         '2024-04-24 16:00')
        self.path.return_value.exists.assert_not_called()

        path_attrs = {'exists.return_value': False}
        self.path.return_value.configure_mock(**path_attrs)
        null_update_tracker = Update_Tracker(self.project)
        self.assertEqual(null_update_tracker.get_updated_since(),
                         Update_Tracker.NULL_TIMESTAMP)

        path_attrs = {'exists.return_value': True}
        self.path.return_value.configure_mock(**path_attrs)
        # The update tracker remains cached.
        self.assertEqual(null_update_tracker.get_updated_since(),
                         Update_Tracker.NULL_TIMESTAMP)

        file_attrs = {'read.return_value': '2024-04-24 20:44'}
        file = self.path.return_value.open.return_value.__enter__.return_value
        file.configure_mock(**file_attrs)
        update_tracker = Update_Tracker(self.project)
        self.assertEqual(update_tracker.get_updated_since(), '2024-04-24 20:44')
        self.path.return_value.open.assert_called_once_with('r',
                                                            encoding='utf-8')

    def test_save_updated_since(self) -> None:
        """
        Test storing a new latest update time.
        """

        update_tracker = Update_Tracker(self.project)
        self.path.assert_called_with(Path('export/TEST'), 'jira-updated.txt')
        update_tracker.save_updated_since('2024-04-24 22:40')
        self.path.return_value.open.assert_called_once_with('w',
                                                            encoding='utf-8')
        file = self.path.return_value.open.return_value.__enter__.return_value
        file.write.assert_called_once_with('2024-04-24 22:40')
