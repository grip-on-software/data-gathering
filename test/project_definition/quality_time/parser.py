"""
Tests for module that parses project definitions from Quality-time.

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
from typing import List, Dict
import unittest
from gatherer.project_definition.base import MetricNames
from gatherer.project_definition.quality_time.parser import Project_Parser, \
    Sources_Parser, Measurements_Parser, Metric_Defaults_Parser, \
    Metric_Options_Parser, Report, Measurement
from gatherer.utils import convert_local_datetime, format_date

def _convert_date(date: str) -> str:
    return format_date(convert_local_datetime(datetime.fromisoformat(date)))

class ProjectParserTest(unittest.TestCase):
    """
    Tests for SonarQube project parser that retrieves the project name.
    """

    def setUp(self) -> None:
        self.parser = Project_Parser({'version_id': '12345'})

    def test_parse(self) -> None:
        """
        Test parsing the definition.
        """

        contents_path = Path('test/sample/quality-time_report.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents: Dict[str, List[Report]] = json.load(contents_file)

        self.parser.load_definition('', contents)
        self.assertEqual(self.parser.parse(), {
            'quality_display_name': 'Demo report'
        })

    def test_parse_report(self) -> None:
        """
        Test parsing a report from a Quality-time server.
        """

        self.parser.parse_report(0, {'title': 'Foo'})
        # Extra reports are ignored.
        self.parser.parse_report(1, {'title': 'Bar'})
        self.assertEqual(self.parser.data, {
            'quality_display_name': 'Foo'
        })

class SourcesParserTest(unittest.TestCase):
    """
    Tests for Quality-time parser that extracts source URLs for the metrics
    specified in a report.
    """

    def test_parse_report(self) -> None:
        """
        Test parsing a report from a Quality-time server.
        """

        contents_path = Path('test/sample/quality-time_report.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents: Dict[str, List[Report]] = json.load(contents_file)

        parser = Sources_Parser({'version_id': '12345'})
        parser.parse_report(0, contents['reports'][0])
        self.assertEqual(parser.data, {
            'Demo application': {
                'sonarqube': {('https://sonar.test', 'demo', 'software')},
                'cloc': {'http://data.test/cloc.json'}
            }
        })

class MeasurementsParserTest(unittest.TestCase):
    """
    Tests for Quality-time parser that formats measurements of metrics.
    """

    def test_parse(self) -> None:
        """
        Test parsing the measurements.
        """

        metrics: MetricNames = {
            '3edbace9-8e2c-4c1d-8e62-7a9fb40ae127': {
                'base_name': 'coverage',
                'domain_name': 'Demo application',
                'scale': 'count'
            }
        }

        measurements_path = Path('test/sample/quality-time_measurements.json')
        with measurements_path.open('r', encoding='utf-8') as measurements_file:
            measurements_response: Dict[str, List[Measurement]] = \
                json.load(measurements_file)

        measurements = measurements_response['measurements']

        parser = Measurements_Parser(metrics=metrics,
                                     measurements=deepcopy(measurements),
                                     version={'version_id': '12345'})
        result = [
            {
                'name': '3edbace9-8e2c-4c1d-8e62-7a9fb40ae127',
                'value': '108163',
                'category': 'target_met',
                'date': _convert_date('2024-05-18T13:05:06+00:00'),
                'since_date': _convert_date('2024-05-04T13:11:21+00:00')
            }
        ]
        self.assertEqual(parser.parse(), {'12345': result})

        # If there are no measurements, then an empty result is returned.
        self.assertEqual(Measurements_Parser().parse(), {})

        measurements.append({
            'metric_uuid': 'unknown',
            'start': '2024-05-18T13:37:26+00:00',
            'end': '2024-05-18T15:57:48+00:00',
            'count': {
                'value': '<unparseable>',
                'status': 'unknown',
                'status_start': '2024-05-18T13:37:26+00:00',
            }
        })
        measurements.append({
            'metric_uuid': 'a-b-c-d',
            'start': '2024-05-18T13:37:26+00:00',
            'end': '2024-05-18T15:57:48+00:00',
            'count': '???',
            'percentage': {
                'value': '42',
                'status': 'target_not_met',
                'status_start': '2024-05-18T13:37:26+00:00',
            }
        })
        result.append({
            'name': 'a-b-c-d',
            'value': '-1',
            'category': 'unknown',
            'date': _convert_date('2024-05-18T15:57:48+00:00'),
            'since_date': _convert_date('2024-05-18T13:37:26+00:00')
        })

        # If there are no metrics, we can still parse count values.
        count = Measurements_Parser(measurements=deepcopy(measurements),
                                    version={'version_id': '56789'})

        self.assertEqual(count.parse(), {'56789': result})

class MetricDefaultsParserTest(unittest.TestCase):
    """
    Tests for Quality-time parser that extracts default metric properties from
    the data model.
    """

    def test_parse(self) -> None:
        """
        Test parsing the metrics.
        """

        datamodel_path = Path('test/sample/quality-time_datamodel.json')
        with datamodel_path.open('r', encoding='utf-8') as datamodel_file:
            data_model = json.load(datamodel_file)

        parser = Metric_Defaults_Parser(data_model=data_model,
                                        version={'version_id': '12345'})
        self.assertEqual(parser.parse(), {
            '12345': [{
                'base_name': 'loc',
                'version_id': '2024-05-18T12:50:04+00:00',
                'commit_date': _convert_date('2024-05-18T12:50:04+00:00'),
                'direction': '-1',
                'target_value': '30000',
                'low_target_value': '35000',
                'scale': 'count'
            }]
        })

        # If there is no version, then an empty result is returned.
        self.assertEqual(Metric_Defaults_Parser().parse(), {})

class MetricOptionsParserTest(unittest.TestCase):
    """
    Tests for Quality-time parser that extracts targets for metrics specified
    in a report.
    """

    def test_parse_report(self) -> None:
        """
        Test parsing a report from a Quality-time server.
        """

        datamodel_path = Path('test/sample/quality-time_datamodel.json')
        with datamodel_path.open('r', encoding='utf-8') as datamodel_file:
            data_model = json.load(datamodel_file)

        contents_path = Path('test/sample/quality-time_report.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents: Dict[str, List[Report]] = json.load(contents_file)

        parser = Metric_Options_Parser(data_model=data_model,
                                       version={'version_id': '12345'})
        parser.parse_report(0, contents['reports'][0])
        self.assertEqual(parser.data, {
            '3ddbacd8-882c-4c0c-8f63-7f9fb00ade27': {
                'base_name': 'loc',
                'domain_name': 'Demo application',
                'scale': 'count',
                'number_of_sources': '1',
                'low_target': '50000',
                'target': '40000',
                'debt_target': '',
                'comment': '',
                'report_uuid': '818b0b22-1bac-45b9-9f4d-ad898a7c47e0',
                'report_date': _convert_date('2024-05-04T13:39:30+00:00'),
                'domain_type': 'software'
            },
            '3edbace9-8e2c-4c1d-8e62-7a9fb40ae127': {
                'base_name': 'loc',
                'domain_name': 'Demo application',
                'scale': 'percentage',
                'number_of_sources': '1',
                'low_target': '40',
                'target': '50',
                'debt_target': '',
                'comment': '',
                'report_uuid': '818b0b22-1bac-45b9-9f4d-ad898a7c47e0',
                'report_date': _convert_date('2024-05-04T13:39:30+00:00'),
                'domain_type': 'software'
            }
        })
