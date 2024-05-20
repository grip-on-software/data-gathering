"""
Tests for module that tracks updates between versions of a project definition.

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
from typing import Dict, Type, Union
import unittest
from unittest.mock import patch, MagicMock
from gatherer.domain.project import Project
from gatherer.domain.source import Source
from gatherer.project_definition.update import Update_Tracker

class MetricDifferenceTest(unittest.TestCase):
    """
    Tests for class that determines whether metric options were changed.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.source = Source.from_type('sonar', name='NewName',
                                       url='https://sonar.test/')
        path = patch('gatherer.project_definition.update.Path', autospec=True)
        self.path = path.start()
        self.path.return_value = Path('test/sample/metric_options_update.json')
        self.addCleanup(path.stop)
        self.tracker = Update_Tracker(self.project, self.source)

    def test_get_start_revision(self) -> None:
        """
        Test retrieving the revision at which to collect new versions.
        """

        self.assertEqual(self.tracker.get_start_revision('12345'), '12345')
        self.assertEqual(self.tracker.get_start_revision(),
                         '2024-05-16T17:28:39.45678+0000')

    def test_get_previous_data(self) -> None:
        """
        Test retrieving the metadata collected from the latest version.
        """

        self.assertEqual(self.tracker.get_previous_data(), {
            'metric_domain': {
                'base_name': 'metric',
                'domain_name': 'domain',
                'version_id': '2024-05-16T17:28:39.45678+0000',
                'target_value': '123',
                'direction': '-1'
            }
        })

        # If the file could not be read, then the previous data is empty.
        attrs = {'exists.return_value': False}
        self.path.return_value = MagicMock(**attrs)
        tracker = Update_Tracker(self.project, self.source)
        self.assertEqual(tracker.get_previous_data(), {})

    @patch('os.utime')
    @patch.object(Project, 'make_export_directory')
    @patch('json.dump')
    def test_set_end(self, dumper: MagicMock, exporter: MagicMock,
                     timer: MagicMock) -> None:
        """
        Test storing the new state of the data from the project definitions.
        """

        self.tracker.set_end(None, None)
        source = {
            "type": "sonar",
            "name": "NewName",
            "url": "https://sonar.test/"
        }
        self.assertIn(source, self.project.sources)
        timer.assert_called_once_with(self.path.return_value, None)

        attrs: Dict[str, Union[bool, Type[Exception]]] = {
            'exists.return_value': False
        }
        self.path.return_value = MagicMock(**attrs)
        tracker = Update_Tracker(self.project, self.source)
        metric_targets = {
            'foo_bar': {
                'base_name': 'foo',
                'domain_name': 'bar',
                'target_value': '456',
                'direction': '-1'
            }
        }
        data = {
            'sources': [source],
            'versions': {
                'https://sonar.test/': '67890'
            },
            'targets': metric_targets
        }
        tracker.set_end('67890', metric_targets)
        exporter.assert_called_once_with()
        file = self.path.return_value.open
        file.assert_called_once_with('w', encoding='utf-8')
        dumper.assert_called_once_with(data,
                                       file.return_value.__enter__.return_value)

        attrs['open.side_effect'] = FileNotFoundError
        self.path.return_value.configure_mock(**attrs)
        dumper.reset_mock()
        tracker.set_end('99999', None)
        dumper.assert_not_called()
