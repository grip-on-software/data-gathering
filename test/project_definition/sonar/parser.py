"""
Tests for module that parses project definitions from SonarQube.

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

import json
from pathlib import Path
from typing import Any, List, Dict
import unittest
from gatherer.project_definition.base import MetricNames
from gatherer.project_definition.sonar.parser import Project_Parser, \
    Sources_Parser, Measurements_Parser, Metric_Defaults_Parser, \
    Metric_Options_Parser

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

        contents_path = Path('test/sample/sonar_search_projects.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents: Dict[str, List[Dict[str, str]]] = json.load(contents_file)

        self.parser.load_definition('', contents)
        self.assertEqual(self.parser.parse(), {
            'quality_display_name': 'Test Organization'
        })

        del contents['organizations']
        self.parser.load_definition('foo', contents)
        self.assertEqual(self.parser.parse(), {
            'quality_display_name': 'Foo'
        })

    def test_parse_component(self) -> None:
        """
        Test parsing a component from a SonarQube server.
        """

        self.parser.parse_component(0, {
            'key': 'foo',
            'name': 'Foo'
        })
        self.parser.parse_component(1, {
            'key': 'bar',
            'name': 'Bar'
        })
        self.assertEqual(self.parser.data, {'quality_display_name': 'Foo'})

class SourcesParserTest(unittest.TestCase):
    """
    Tests for SonarQube parser that extracts source URL from project components.
    """

    def test_parse_component(self) -> None:
        """
        Test parsing a component from a SonarQube server.
        """

        contents_path = Path('test/sample/sonar_navigation_component.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents: Dict[str, Any] = json.load(contents_file)

        parser = Sources_Parser({'version_id': '12345'})
        parser.parse_component(0, contents)
        self.assertEqual(parser.data, {
            'Foo': {'github': ['https://github.test/org/foo']}
        })
        parser.parse_component(1, {'key': 'bar', 'name': 'Bar'})
        self.assertNotIn('Bar', parser.data)

class MeasurementsParserTest(unittest.TestCase):
    """
    Tests for SonarQube parser that formats measurements of metrics.
    """

    def test_parse(self) -> None:
        """
        Test parsing the measurements.
        """

        metrics: MetricNames = {
            'metric1_foo': {
                'base_name': 'metric1',
                'domain_name': 'foo',
                'target_value': '2',
                'perfect_value': '1',
                'direction': '-1'
            }
        }

        measurements_path = Path('test/sample/sonar_measures_history.json')
        with measurements_path.open('r', encoding='utf-8') as measurements_file:
            history: Dict[str, List[Dict[str, List[Dict[str, str]]]]] = \
                json.load(measurements_file)

        measurements = history['measures'][0]['history']
        for measurement in measurements:
            measurement['base_name'] = 'metric1'
            measurement['domain_name'] = 'foo'

        parser = Measurements_Parser(metrics=metrics,
                                     measurements=measurements,
                                     version={'version_id': '12345'})
        self.assertEqual(parser.parse(), {
            '12345': [
                {
                    'name': 'metric1_foo',
                    'value': '1',
                    'category': 'perfect',
                    'date': '2024-05-06 07:08:09'
                },
                {
                    'name': 'metric1_foo',
                    'value': '2',
                    'category': 'green',
                    'date': '2024-05-16 17:18:19'
                }
            ]
        })

        # If there are no measurements, then an empty result is returned.
        self.assertEqual(Measurements_Parser().parse(), {})

        measurements = [
            {
                'base_name': 'metric2',
                'domain_name': 'bar',
                'date': '2024-05-18T16:03:12+0000',
                'value': '<invalid>'
            },
            {
                'base_name': 'metric2',
                'domain_name': 'bar',
                'date': '2024-05-18T16:03:12+0000',
                'value': '20.0'
            }
        ]

        # If there are no metrics, we can still parse valid values.
        nameless = Measurements_Parser(measurements=measurements,
                                       version={'version_id': '56789'})
        self.assertEqual(nameless.parse(), {
            '56789': [
                {
                    'name': 'metric2_bar',
                    'value': '20.0',
                    'category': 'grey',
                    'date': '2024-05-18 16:03:12'
                }
            ]
        })

class MetricDefaultsParserTest(unittest.TestCase):
    """
    Tests for SonarQube parser that extracts default metric properties.
    """

    def test_parse(self) -> None:
        """
        Test parsing the metrics.
        """

        metrics = {
            'metric1': {
                'key': 'metric1',
                'type': 'INT',
                'direction': 1
            },
            'metric2': {
                'key': 'metric2',
                'type': 'WORK_DUR'
            },
            'metric3': {
                'key': 'metric3',
                'type': 'UNKNOWN'
            }
        }

        parser = Metric_Defaults_Parser(data_model=metrics,
                                        version={'version_id': '12345'})
        self.assertEqual(parser.parse(), {
            '12345': [
                {
                    'base_name': 'metric1',
                    'direction': '1',
                    'scale': 'count',
                    'version_id': '12345'
                },
                {
                    'base_name': 'metric2',
                    'scale': 'duration',
                    'direction': '-1',
                    'perfect_value': '0',
                    'version_id': '12345'
                },
                {
                    'base_name': 'metric3',
                    'direction': '-1',
                    'version_id': '12345'
                }
            ]
        })

        # If there is no version, then an empty result is returned.
        self.assertEqual(Metric_Defaults_Parser().parse(), {})

class MetricOptionsParserTest(unittest.TestCase):
    """
    Tests for SonarQube parser that extracts targets for metrics specified in
    the quality gate.
    """

    def test_parse(self) -> None:
        """
        Test parsing the metrics.
        """

        metrics = {
            'metric1': {
                'key': 'metric1',
                'type': 'INT',
                'direction': 1
            }
        }

        contents_path = Path('test/sample/sonar_search_projects.json')
        with contents_path.open('r', encoding='utf-8') as contents_file:
            contents = json.load(contents_file)

        parser = Metric_Options_Parser(data_model=metrics,
                                       version={'version_id': '12345'})
        parser.load_definition('', contents)
        self.assertEqual(parser.parse(), {
            'metric1_foo': {
                'base_name': 'metric1',
                'domain_name': 'foo',
                'direction': '1',
                'scale': 'count',
                'version_id': '12345',
                'default': '1'
            }
        })

        # If there is no version, then an empty result is returned.
        self.assertEqual(Metric_Options_Parser().parse(), {})
