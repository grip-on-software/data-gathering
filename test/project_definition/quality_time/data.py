"""
Tests for module that provides the data connection for the project reports
and metrics at a Quality-time server.

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
import unittest
from unittest.mock import patch, MagicMock
import dateutil.tz
from requests.exceptions import ConnectionError as ConnectError
import requests_mock
from gatherer.domain.project import Project
from gatherer.domain.source import Source
from gatherer.project_definition.base import MetricNames
from gatherer.project_definition.quality_time.data import Quality_Time_Data
from gatherer.utils import convert_local_datetime, format_date, get_utc_datetime

class SonarDataTest(unittest.TestCase):
    """
    Tests for project definition stored in a SonarQube server.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.source = Source.from_type('quality-time', name='Quality time',
                                       url='https://qt.test')

        self.request = requests_mock.Mocker()
        self.request.start()
        self.addCleanup(self.request.stop)

        self.data = Quality_Time_Data(self.project, self.source)

    @staticmethod
    def _make_date(date: datetime) -> str:
        # Format a commit date
        return format_date(convert_local_datetime(date))

    @patch('gatherer.project_definition.quality_time.data.datetime')
    def test_get_versions(self, date: MagicMock) -> None:
        """
        Test receiving a sequence of version metadata.
        """

        now = datetime(2024, 5, 17, 19, 21, 33, tzinfo=dateutil.tz.tzutc())
        attrs = {'now.return_value': now}
        date.configure_mock(**attrs)

        version = {
            'version_id': '2024-05-17T19:21:33+00:00',
            'commit_date': self._make_date(now)
        }
        self.assertEqual(self.data.get_versions(None, None), [version])
        self.assertEqual(self.data.get_latest_version(), version)
        self.assertEqual(self.data.get_versions(None, '2024-05-17 19:21:33'),
                         [version])

    def test_get_start_version(self) -> None:
        """
        Test retrieving version metadata to start collecting data from if no
        other version is known.
        """

        start_date = get_utc_datetime('1970-01-01 00:00:00')
        self.assertEqual(self.data.get_start_version(), {
            'version_id': '1970-01-01T00:00:00+00:00',
            'commit_date': self._make_date(start_date)
        })

    def test_get_contents(self) -> None:
        """
        Test retrieving the contents of a project definition.
        """

        response_path = Path('test/sample/quality-time_report.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        report_uuid = '818b0b22-1bac-45b9-9f4d-ad898a7c47e0'

        self.request.get('https://qt.test/api/internal/report/',
                         json=response)
        self.request.get(f'https://qt.test/api/internal/report/{report_uuid}',
                         json=response)

        self.assertEqual(self.data.get_contents(self.data.get_latest_version()),
                         response)

        # If an identifier is encoded in the URL, then the result is filtered.
        data = Quality_Time_Data(self.project, self.source,
                                 url=f'https://qt.test/{report_uuid}')
        self.assertEqual(data.get_contents(data.get_latest_version()), response)
        if self.request.last_request is None:
            self.fail('Request was not performed')
        self.assertEqual(self.request.last_request.path,
                         f'/api/internal/report/{report_uuid}')

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://qt.test/api/internal/report/',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.get_contents(self.data.get_latest_version())

    def test_get_data_model(self) -> None:
        """
        Test receiving the project definition data model.
        """

        response_path = Path('test/sample/quality-time_datamodel.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        self.request.get('https://qt.test/api/internal/datamodel',
                         json=response)

        data_model = self.data.get_data_model(self.data.get_latest_version())
        self.assertEqual(data_model, response)

        # If the request has an error, then a RuntimeError is raised.
        self.request.get('https://qt.test/api/internal/datamodel',
                         exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.get_data_model(self.data.get_latest_version())

    def test_adjust_target_versions(self) -> None:
        """
        Test updating metric target version information to enrich with more
        details.
        """

        response_path = Path('test/sample/quality-time_changelog.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        metric_uuid = '3edbace9-8e2c-4c1d-8e62-7a9fb40ae127'
        url = f'https://qt.test/api/internal/changelog/metric/{metric_uuid}/10'
        self.request.get(url, json=response)

        version = {'version_id': '2024-05-04T13:45:00+00:00'}
        metrics = {
            metric_uuid: {
                'base_name': 'loc',
                'report_uuid': '818b0b22-1bac-45b9-9f4d-ad898a7c47e0',
                'report_date': '2024-05-04 13:39:32',
                'domain_name': 'Demo application',
                'domain_type': 'software',
                'scale': 'count',
                'target': '40000',
                'low_target': '50000'
            }
        }

        # Expected state for first change with only 'target' change
        version_metrics = deepcopy(metrics)
        version_metrics[metric_uuid]['scale'] = 'count'
        version_metrics[metric_uuid]['low_target'] = '35000'

        versions = self.data.adjust_target_versions(version, deepcopy(metrics))
        self.assertEqual(len(versions), 4)

        self.assertEqual(versions[0][0], {
            "developer": "Jane Doe",
            "email": "janedoe@example.test",
            "message": "",
            "version_id": "2024-05-04T13:27:42+00:00",
            "commit_date": self._make_date(datetime(2024, 5, 4, 13, 27, 42,
                                                    tzinfo=dateutil.tz.tzutc()))
            })
        self.assertEqual(versions[0][1], version_metrics)

        version_metrics[metric_uuid]['low_target'] = '50000'
        self.assertEqual(versions[1][0], {
            "developer": "Jane Doe",
            "email": "janedoe@example.test",
            "message": "",
            "version_id": "2024-05-04T13:27:44+00:00",
            "commit_date": self._make_date(datetime(2024, 5, 4, 13, 27, 44,
                                                    tzinfo=dateutil.tz.tzutc()))
        })
        self.assertEqual(versions[1][1], version_metrics)

        version_metrics[metric_uuid]['scale'] = 'percentage'
        self.assertEqual(versions[2][0], {
            "developer": "Jane Doe",
            "email": "janedoe@example.test",
            "message": "",
            "version_id": "2024-05-04T13:39:23+00:00",
            "commit_date": self._make_date(datetime(2024, 5, 4, 13, 39, 23,
                                                    tzinfo=dateutil.tz.tzutc()))
        })
        self.assertEqual(versions[2][1], version_metrics)

        version_metrics[metric_uuid]['scale'] = 'count'
        self.assertEqual(versions[3][0], {
            "developer": "Jane Doe",
            "email": "janedoe@example.test",
            "message": "",
            "version_id": "2024-05-04T13:39:30+00:00",
            "commit_date": self._make_date(datetime(2024, 5, 4, 13, 39, 30,
                                                    tzinfo=dateutil.tz.tzutc()))
        })
        self.assertEqual(versions[3][1], version_metrics)

        # If a start revision is given, then not all versions are collected.
        middle_date = '2024-05-04T13:37:42+00:00'
        versions = self.data.adjust_target_versions(version, deepcopy(metrics),
                                                    from_revision=middle_date)
        self.assertEqual(len(versions), 2)

        # If the start revision is old enough, then no versions are collected.
        end_date = '2024-05-04T13:39:32+00:00'
        versions = self.data.adjust_target_versions(version, deepcopy(metrics),
                                                    from_revision=end_date)
        self.assertEqual(len(versions), 0)

        # If the request has an error, then a RuntimeError is raised.
        self.request.get(url, exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.adjust_target_versions(version, metrics)

    def test_get_measurements(self) -> None:
        """
        Test retrieving the measurements for quality metrics measured at
        the project definition.
        """

        response_path = Path('test/sample/quality-time_measurements.json')
        with response_path.open('r', encoding='utf-8') as response_file:
            response = json.load(response_file)

        metric_uuid = '3edbace9-8e2c-4c1d-8e62-7a9fb40ae127'
        url = f'https://qt.test/api/internal/measurements/{metric_uuid}'
        self.request.get(url, json=response)

        metrics: MetricNames = {
            metric_uuid: {
                'base_name': 'loc',
                'domain_name': 'Demo application'
            },
            'ignore': {}
        }
        version = {'version_id': '2024-05-04T13:45:00+00:00'}

        measurements = self.data.get_measurements(metrics, version)
        self.assertEqual(measurements, response['measurements'])

        end_date = '2024-05-18T13:45:56+00:00'

        # If a start revision is provided, then metrics are cut off.
        self.assertEqual(self.data.get_measurements(metrics, version,
                                                    from_revision=end_date), [])

        # If no metrics are provided, then a RuntimeError is raised.
        with self.assertRaises(RuntimeError):
            self.data.get_measurements(None, version)

        # If the request has an error, then a RuntimeError is raised.
        self.request.get(url, exc=ConnectError)
        with self.assertRaises(RuntimeError):
            self.data.get_measurements(metrics, version)
