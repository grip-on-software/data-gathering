"""
Tests for module that compares versions of metric options.

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

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from gatherer.domain.project import Project
from gatherer.project_definition.metric import Metric_Difference

class MetricDifferenceTest(unittest.TestCase):
    """
    Tests for class that determines whether metric options were changed.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')

    def test_add_version(self) -> None:
        """
        Test checking whether the version contains unique changes.
        """

        metric = Metric_Difference(self.project, previous_targets={})
        targets = {
            'metric1': {
                'target_value': '1',
                'direction': '-1'
            },
            'metric2': {
                'target_value': '2.00',
                'direction': '1'
            }
        }
        metric.add_version({'version_id': '1234'}, targets)
        self.assertEqual(metric.previous_metric_targets, targets)

        metric.add_version({'version_id': '2345'}, deepcopy(targets))
        self.assertEqual(metric.previous_metric_targets, targets)

        new_targets = {
            'metric1': {
                'target_value': '10',
                'direction': '-1'
            },
            'metric2': {
                'target_value': '2.00',
                'direction': '1'
            },
            'metric3': {
                'target_value': '50',
                'direction': '1'
            }
        }
        metric.add_version({'version_id': '3456'}, new_targets)
        self.assertEqual(metric.previous_metric_targets, new_targets)

        self.assertEqual(metric.unique_versions, [
            {'version_id': '1234'},
            {'version_id': '3456'}
        ])
        unique_targets = [
            {
                'name': 'metric1',
                'revision': '1234',
                'target_value': '1',
                'direction': '-1'
            },
            {
                'name': 'metric2',
                'revision': '1234',
                'target_value': '2.00',
                'direction': '1'
            },
            {
                'name': 'metric1',
                'revision': '3456',
                'target_value': '10',
                'direction': '-1'
            },
            {
                'name': 'metric3',
                'revision': '3456',
                'target_value': '50',
                'direction': '1'
            }
        ]
        self.assertEqual(metric.unique_metric_targets, unique_targets)

    @patch('gatherer.project_definition.metric.Key_Table', autospec=True)
    @patch('gatherer.project_definition.metric.Table', autospec=True)
    def test_export(self, table: MagicMock, key_table: MagicMock) -> None:
        """
        Test saving the unique metric data to JSON.
        """

        metric = Metric_Difference(self.project)
        metric.export()
        export_key = Path('export/TEST')
        key_table.assert_called_once_with('metric_versions', 'version_id')
        key_table.return_value.write.assert_called_once_with(export_key)
        table.assert_called_once_with('metric_targets')
        table.return_value.write.assert_called_once_with(export_key)
