"""
Tests for module that provides the data connection for the project definitions
and metrics at a SonarQube server.

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
from datetime import datetime
import json
from pathlib import Path
from typing import List, MutableMapping, Union
import unittest
from unittest.mock import patch, MagicMock
import dateutil.tz
from requests.exceptions import ConnectionError as ConnectError
import requests_mock
from gatherer.domain.project import Project
from gatherer.domain.source import Source
from gatherer.project_definition.base import MetricNames
from gatherer.project_definition.sonar.data import Sonar_Data

Metric = MutableMapping[str, Union[str, bool]]
MetricResponse = MutableMapping[str, Metric]
MetricTargets = MutableMapping[str, MutableMapping[str, str]]

class SonarDataTest(unittest.TestCase):
    """
    Tests for project definition stored in a SonarQube server.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.source = Source.from_type('sonar', name='SonarQube',
                                       url='https://sonar.test')

        self.request = requests_mock.Mocker()
        self.request.start()
        self.addCleanup(self.request.stop)
        self.request.get('https://sonar.test/api/server/version', text='10.6')

        self.data = Sonar_Data(self.project, self.source)

    @patch('gatherer.project_definition.sonar.data.datetime')
    def test_get_versions(self, date: MagicMock) -> None:
        """
        Test receiving a sequence of version metadata.
        """

        now = datetime(2024, 5, 17, 19, 21, 33, tzinfo=dateutil.tz.tzlocal())
        attrs = {'now.return_value': now}
        date.configure_mock(**attrs)

        offset = now.utcoffset()
        hours, minutes = 0, 0
        if offset is not None:
            hours = int(offset.total_seconds() / 3600)
            minutes = int((offset.total_seconds() % 3600) / 60)

        version = [
            {
                'version_id': f'2024-05-17T19:21:33{hours:+03}{minutes:02}',
                'commit_date': '2024-05-17 19:21:33'
            }
        ]
        self.assertEqual(self.data.get_versions(None, None), version)
        self.assertEqual(self.data.get_latest_version(), version[0])
        self.assertEqual(self.data.get_versions(None, '2024-05-17 19:21:33'),
                         version)

    def test_get_start_version(self) -> None:
        """
        Test retrieving version metadata to start collecting data from if no
        other version is known.
        """

        then = datetime(1970, 1, 1, 0, 0, 0, tzinfo=dateutil.tz.tzlocal())
        offset = then.utcoffset()
        hours, minutes = 0, 0
        if offset is not None:
            hours = int(offset.total_seconds() / 3600)
            minutes = int((offset.total_seconds() % 3600) / 60)
        self.assertEqual(self.data.get_start_version(), {
            'version_id': f'1970-01-01T00:00:00{hours:+03}{minutes:02}',
            'commit_date': '1970-01-01 00:00:00'
        })

    def test_get_contents(self) -> None:
        """
        Test retrieving the contents of a project definition.
        """

        response_path = Path('test/sample/sonar_search_projects.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        self.request.get('https://sonar.test/api/components/search_projects',
                         json=response)

        self.assertEqual(self.data.get_contents(self.data.get_latest_version()),
                         response)

        # If an identifier is encoded in the URL, then the result is filtered.
        data = Sonar_Data(self.project, self.source,
                          url='https://sonar.test/project/overview?id=foo')
        self.assertEqual(data.get_contents(data.get_latest_version()), response)
        if self.request.last_request is None:
            self.fail('Request was not performed')
        self.assertEqual(self.request.last_request.qs, {
            'f': ['_all'],
            's': ['analysisDate'],
            'asc': ['no'],
            'filter': ['query="foo"'],
            'p': ['1'],
            'ps': ['100']
        })

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://sonar.test/api/components/search_projects',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            data.get_contents(data.get_latest_version())

    def test_update_source_definitions(self) -> None:
        """
        Test updating a source definition to enrich it with more details on
        sources.
        """

        contents_path = Path('test/sample/sonar_search_projects.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents = json.load(contents_file)

        response_path = Path('test/sample/sonar_navigation_component.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        original = deepcopy(contents)
        result = deepcopy(contents)
        result['components'][0].update(deepcopy(response))

        self.request.get('https://sonar.test/api/navigation/component',
                         json=response)
        self.data.update_source_definitions(contents)
        self.assertEqual(contents, result)

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://sonar.test/api/navigation/component',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.update_source_definitions(original)

    @staticmethod
    def _make_metrics(count: int, domain_name: str = '') -> MetricTargets:
        metrics: MetricTargets = {}
        for index in range(count):
            base_name = f'metric{index}'
            metrics[f'{base_name}_{domain_name}'] = {
                'id': str(index),
                'key': base_name,
                'type': 'INT',
                'name': f'Test Metric {index}',
                'description': f'Test Metric {index}',
                'domain': 'software',
                'base_name': base_name,
                'domain_name': domain_name
            }

        return metrics

    @staticmethod
    def _adjust_metric_response(metrics: MetricTargets) -> List[Metric]:
        response: List[Metric] = []
        for index, metric in enumerate(metrics.values()):
            metric_response: Metric = dict(metric)
            metric_response.update({
                'qualitative': index % 2 == 0,
                'hidden': index % 5 == 0
            })
            response.append(metric_response)
        return response

    def test_get_data_model(self) -> None:
        """
        Test receiving the project definition data model.
        """

        page = {
            'total': 121,
            'p': 1,
            'ps': 120,
            'metrics': self._adjust_metric_response(self._make_metrics(120))
        }

        self.request.get('https://sonar.test/api/metrics/search?p=1&ps=120',
                         json=page)
        self.request.get('https://sonar.test/api/metrics/search?p=2&ps=120',
                         json={
                             'total': 121,
                             'p': 2,
                             'ps': 120,
                             'metrics': [
                                 {
                                     'id': 4242,
                                     'key': 'coverage',
                                     'type': 'PERCENT',
                                     'qualitative': True
                                 }
                             ]
                         })

        data_model = self.data.get_data_model(self.data.get_latest_version())
        self.assertEqual(list(data_model.keys()), [
            f'metric{number}' for number in range(0, 120, 2)
            if number % 10 != 0
        ] + ['coverage'])

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://sonar.test/api/metrics/search?p=1&ps=120',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.get_data_model(self.data.get_latest_version())

    def test_adjust_target_versions(self) -> None:
        """
        Test updating metric target version information to enrich with more
        details.
        """

        foo_metrics = self._make_metrics(10, 'foo')
        bar_metrics = self._make_metrics(10, 'bar')
        metrics: MetricNames = {
            key: dict(metric) for key, metric in foo_metrics.items()
        }
        metrics.update({
            key: dict(metric) for key, metric in bar_metrics.items()
        })
        metrics['baz_invalid'] = None

        self.request.get('https://sonar.test/api/qualitygates/get_by_project?project=foo',
                         json={'qualityGate': {
                             'id': 9,
                             'name': 'Sonar way',
                             'default': True
                         }})
        self.request.get('https://sonar.test/api/qualitygates/get_by_project?project=bar',
                         json={'qualityGate': {
                             'id': 10,
                             'name': 'Custom',
                             'default': False
                         }})
        self.request.get('https://sonar.test/api/qualitygates/show?name=Custom',
                         json={
                             'id': 9,
                             'name': 'Sonar way',
                             'conditions': [
                                 {
                                     'id': 33,
                                     'metric': 'new_coverage',
                                     'op': 'LT',
                                     'error': '80'
                                 },
                                 {
                                     'id': 77,
                                     'metric': 'metric1',
                                     'op': 'GT',
                                     'error': '22'
                                 },
                              ],
                             'isBuiltIn': False
                         })

        expected: MetricNames = {
            key: dict(metric) for key, metric in foo_metrics.items()
        }
        bar_metrics['metric1_bar']['target'] = '22'
        expected.update({
            key: dict(metric) for key, metric in bar_metrics.items()
        })
        expected['baz_invalid'] = None

        version = self.data.get_latest_version()
        target_versions = self.data.adjust_target_versions(version,
                                                           dict(metrics))
        self.assertEqual(target_versions, [(version, expected)])

        # Requests with an error lead to a RuntimeError.
        self.request.get('https://sonar.test/api/qualitygates/show?name=Custom',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.adjust_target_versions(version, dict(metrics))

        self.request.get('https://sonar.test/api/qualitygates/get_by_project?project=foo',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.adjust_target_versions(version, dict(metrics))

    def test_get_measurements(self) -> None:
        """
        Test retrieving the measurements for quality metrics measured at the
        project definition.
        """

        response_path = Path('test/sample/sonar_measures_history.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        self.request.get('https://sonar.test/api/measures/search_history',
                         json=response)

        foo_metrics = self._make_metrics(2, 'foo')
        bar_metrics = self._make_metrics(2, 'bar')
        metrics: MetricNames = {
            key: dict(metric) for key, metric in foo_metrics.items()
        }
        metrics.update({
            key: dict(metric) for key, metric in bar_metrics.items()
        })
        metrics['baz_invalid'] = None

        measures = self.data.get_measurements(dict(metrics),
                                              self.data.get_latest_version())
        self.assertEqual(measures, [
            {
                'base_name': 'metric1',
                'domain_name': 'foo',
                'date': '2024-05-06T07:08:09+0000',
                'value': '1'
            },
            {
                'base_name': 'metric1',
                'domain_name': 'foo',
                'date': '2024-05-16T17:18:19+0000',
                'value': '2'
            },
            {
                'base_name': 'metric1',
                'domain_name': 'bar',
                'date': '2024-05-06T07:08:09+0000',
                'value': '1'
            },
            {
                'base_name': 'metric1',
                'domain_name': 'bar',
                'date': '2024-05-16T17:18:19+0000',
                'value': '2'
            }
        ])

        # If no metrics are provided, then a RuntimeError is raised.
        with self.assertRaises(RuntimeError):
            self.data.get_measurements(None, self.data.get_latest_version())

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://sonar.test/api/measures/search_history',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.get_measurements(dict(metrics),
                                       self.data.get_latest_version(),
                                       from_revision='broken request')

    def test_filename(self) -> None:
        """
        Test retrieving a distinguishing filename for the project definition.
        """

        self.assertEqual(self.data.filename, '')

        # If an identifier is encoded in the URL, then the filename uses it.
        data = Sonar_Data(self.project, self.source,
                          url='https://sonar.test/project/overview?id=foo')
        self.assertEqual(data.filename, 'foo')
