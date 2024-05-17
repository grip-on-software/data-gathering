"""
Tests for module that collects data from various versions of project definitions
and related quality metric data.

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
from typing import Any, Dict, List, Optional, Type
import unittest
from unittest.mock import patch, MagicMock
from gatherer.domain.project import Project
from gatherer.domain.source import Source
from gatherer.project_definition.base import Data, Parser, Definition_Parser, \
    Measurement_Parser, Metric_Parser, Version
from gatherer.project_definition.collector import Project_Collector, \
    Sources_Collector, Measurements_Collector, Metric_Defaults_Collector, \
    Metric_Options_Collector
from gatherer.project_definition.metric import Metric_Difference

class MagicClassMock(MagicMock):
    """
    Base class for a magic mock that can be instantiated.
    """

    new_called = False
    new_kwargs: Optional[Dict[str, Any]] = None

    @classmethod
    def assert_instantiated_with(cls, **kwargs: Any) -> None:
        """
        Assert that the mock was instantiated with the specified arguments.
        """

        if not cls.new_called:
            raise AssertionError(f'{cls.__name__} was not instatiated')

        if kwargs != cls.new_kwargs:
            raise AssertionError(f'Expected instance of {cls.__name__} '
                                 f'not found. Expected: {kwargs} '
                                 f'Actual: {cls.new_kwargs}')

def mock_parser_class(parser_class: Type[Parser]) -> Type[MagicClassMock]:
    """
    Create a mock that passes `issubclass` checks for parser types.
    """

    class Meta(MagicClassMock):
        """
        Wrapper class for magic mocks that wraps a parser class.
        """

        return_value = MagicMock(spec=parser_class)

        def __new__(cls, **kwargs: Any):
            cls.new_called = True
            cls.new_kwargs = kwargs
            return cls.return_value

    parser_class.register(Meta)
    return Meta

class CollectorTest(unittest.TestCase):
    """
    Base class for tests of collection process.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.parser = MagicMock()
        self.data = MagicMock(spec=Data)
        self.source = MagicMock(project_definition_class=self.data)

        update = patch('gatherer.project_definition.collector.Update_Tracker',
                       autospec=True)
        self.update_tracker = update.start()
        self.addCleanup(update.stop)

        table = patch('gatherer.project_definition.collector.Table',
                      autospec=True)
        self.table = table.start()
        self.addCleanup(table.stop)

class ProjectCollectorTest(CollectorTest):
    """
    Tests for collector that retrieves project information.
    """

    def test_missing(self) -> None:
        """
        Test setting up a collector with missing project definition data, parser
        or versions.
        """

        # Missing project definition data
        with self.assertRaises(TypeError):
            Project_Collector(self.project,
                              MagicMock(project_definition_class=None))

        # Missing parser
        self.data.return_value.configure_mock(parsers={})

        collector = Project_Collector(self.project, self.source)
        collector.collect_version({'version_id': '10101'})
        self.assertEqual(collector.meta, {})
        with self.assertRaises(RuntimeError):
            collector.get_parser_class()

        # Missing versions from data
        attrs: Dict[str, List[Version]] = {'get_versions.return_value': []}
        self.data.return_value.configure_mock(**attrs)

        collector.collect(from_revision=None, to_revision='99999')
        self.update_tracker.return_value.set_end.assert_called_once_with(None,
                                                                         None)

        # Parser is not a definition parser, raises a RuntimeError upon parsing
        parser = MagicMock()
        parser_attrs = {'parse.side_effect': RuntimeError}
        parser.return_value.configure_mock(**parser_attrs)
        self.data.return_value.configure_mock(parsers={'project_meta': parser})
        collector.collect_version({'version_id': '19357'})
        parser.return_value.load_definition.assert_not_called()
        self.assertEqual(collector.meta, {})

    def test_collect(self) -> None:
        """
        Test collecting data from project definitions.
        """

        version = {'version_id': '24680'}
        attrs = {
            'get_versions.return_value': [version],
            'filename': 'file',
            'parsers': {'project_meta': self.parser}
        }
        self.data.return_value.configure_mock(**attrs)
        self.parser.return_value = MagicMock(spec=Definition_Parser)

        collector = Project_Collector(self.project, self.source)
        self.update_tracker.assert_called_once_with(self.project, self.source,
                                                    target='project_meta')
        self.data.assert_called_once_with(self.project, self.source, None)

        collector.collect('12345', '67890')
        update_tracker = self.update_tracker.return_value
        update_tracker.get_start_revision.assert_called_once_with('12345')

        self.data.return_value.get_contents.assert_called_once_with(version)
        data = self.data.return_value.get_contents.return_value
        self.parser.assert_called_once_with(version=version)
        self.parser.return_value.load_definition.assert_called_once_with('file',
                                                                         data)
        self.assertEqual(collector.meta,
                         self.parser.return_value.parse.return_value)
        update_tracker.set_end.assert_called_once_with('24680', None)

    def test_collect_latest(self) -> None:
        """
        Test collecting data from the latest version of the project definition.
        """

        version = {'version_id': '13579'}
        attrs = {
            'get_latest_version.return_value': version,
            'filename': 'file',
            'parsers': {'project_meta': self.parser}
        }
        self.data.return_value.configure_mock(**attrs)
        self.parser.return_value = MagicMock(spec=Definition_Parser)

        collector = Project_Collector(self.project, self.source)
        collector.collect_latest()
        self.assertEqual(collector.meta,
                         self.parser.return_value.parse.return_value)
        self.update_tracker.return_value.set_end.assert_called_once_with('13579',
                                                                         None)

class SourcesCollectorTest(CollectorTest):
    """
    Tests for collector that retrieves version control sources from project
    definitions.
    """

    def test_get_data(self) -> None:
        """
        Test retrieving unprocessed source data.
        """

        version = {'version_id': '24680'}
        attrs = {'parsers': {'project_sources': self.parser}}
        self.data.return_value.configure_mock(**attrs)
        collector = Sources_Collector(self.project, self.source)
        data = self.data.return_value
        contents = data.get_contents.return_value
        self.assertEqual(collector.get_data(version), contents)
        data.update_source_definitions.assert_called_once_with(contents)

    def test_aggregate_result(self) -> None:
        """
        Test formatting the collected result according to our needs.
        """

        version = {'version_id': '24680'}
        attrs = {'parsers': {'project_sources': self.parser}}
        self.data.return_value.configure_mock(**attrs)
        self.parser.configure_mock(SOURCES_MAP={
                                       'gh': 'github',
                                       'gl': 'gitlab',
                                       'ad': 'tfs',
                                       'sq': 'sonar',
                                       'uh': 'invalid'
                                   },
                                   SOURCES_DOMAIN_FILTER=['business'],
                                   return_value=MagicMock(spec=Definition_Parser))
        result = {
            'foo': {'gh': ['https://github.test/foo/bar']},
            'other': {
                'gl': ['https://gitlab.test/bar/baz'],
                'ad': ['https://tfs.test/_git/repo', None],
                'uh': ['https://invalid.test']
            },
            'metric': {'sq': [
                ('https://sonar.test', 'component_name', 'software'),
                ('https://sonar.test', 'report', 'business')
            ]}
        }

        collector = Sources_Collector(self.project, self.source)
        collector.aggregate_result(version, result)

        self.assertIn(Source.from_type('github', name='foo',
                                       url='https://github.test/foo/bar'),
                      self.project.sources)
        self.assertIn(Source.from_type('gitlab', name='other',
                                       url='https://gitlab.test/bar/baz'),
                      self.project.sources)
        self.assertIn(Source.from_type('tfs', name='other',
                                       url='https://tfs.test/_git/repo'),
                      self.project.sources)
        self.assertIn(Source.from_type('sonar', name='metric',
                                       url='https://sonar.test'),
                      self.project.sources)
        self.assertEqual(len(self.project.sources), 4)

        self.table.assert_called_once_with('source_ids', merge_update=True)
        table = self.table.return_value
        self.assertEqual(table.append.call_count, 2)
        self.assertEqual(table.append.call_args_list[0].args[0], {
            'domain_name': 'metric',
            'url': 'https://sonar.test',
            'source_id': 'component_name',
            'source_type': 'sonar',
            'domain_type': 'software'
        })
        self.assertEqual(table.append.call_args_list[1].args[0], {
            'domain_name': 'metric',
            'url': 'https://sonar.test',
            'source_id': 'report',
            'source_type': 'sonar',
            'domain_type': 'business'
        })

    def test_finish(self) -> None:
        """
        Test finishing retrieving data.
        """

        version = {'version_id': '24680'}
        attrs = {'parsers': {'project_sources': self.parser}}
        self.data.return_value.configure_mock(**attrs)
        self.parser.return_value = MagicMock(spec=Definition_Parser)

        collector = Sources_Collector(self.project, self.source)
        collector.finish(version)
        table = self.table.return_value
        table.write.assert_called_once_with(Path('export/TEST'))

class MeasurementsCollectorTest(CollectorTest):
    """
    Tests for collector that retrieves measurements of metrics.
    """

    def test_build_parser(self) -> None:
        """
        Test retrieving a parser object.
        """

        version = {'version_id': '24680'}

        parser = mock_parser_class(Definition_Parser)
        attrs = {'parsers': {'measurements': parser}}
        self.data.return_value.configure_mock(**attrs)
        with self.assertRaises(TypeError):
            invalid = Measurements_Collector(self.project, self.source)
            invalid.build_parser(version)

        parser = mock_parser_class(Measurement_Parser)
        attrs = {'parsers': {'measurements': parser}}
        self.data.return_value.configure_mock(**attrs)
        collector = Measurements_Collector(self.project, self.source)
        self.assertIsInstance(collector.build_parser(version),
                              Measurement_Parser)

    def test_collect_version(self) -> None:
        """
        Test collecting information.
        """

        version = {'version_id': '24680'}
        self.source.type = 'quality-time'
        parser_class = mock_parser_class(Measurement_Parser)
        parser = parser_class.return_value
        parser_attrs: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            'parse.return_value': {'24680': []}
        }
        parser.configure_mock(**parser_attrs)
        data_attrs = {'parsers': {'measurements': parser_class}}
        data = self.data.return_value
        data.configure_mock(**data_attrs)

        collector = Measurements_Collector(self.project, self.source)
        collector.collect_version(version)

        data.get_measurements.assert_called_once_with(None, version,
                                                      from_revision=None)
        measurements = data.get_measurements.return_value
        parser_class.assert_instantiated_with(metrics=None,
                                              measurements=measurements,
                                              version=version)
        parser.parse.assert_called_once()
        self.table.assert_called_once_with('metrics', merge_update=True)
        table = self.table.return_value
        table.extend.assert_called_once_with([])

class MetricDefaultsCollectorTest(CollectorTest):
    """
    Tests for collector that retrieves default targets for metrics.
    """

    def test_collect(self) -> None:
        """
        Test collecting data from the project definition source.
        """

        version = {'version_id': '24680'}
        parser_class = mock_parser_class(Metric_Parser)
        parser = parser_class.return_value
        parser_attrs: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            'parse.return_value': {'24680': []}
        }
        parser.configure_mock(**parser_attrs)
        attrs = {
            'get_versions.return_value': [version],
            'parsers': {'metric_defaults': parser_class}
        }
        data = self.data.return_value
        data.configure_mock(**attrs)

        collector = Metric_Defaults_Collector(self.project, self.source)
        collector.collect()

        data.get_data_model.assert_called_once_with(version)
        data_model = data.get_data_model.return_value
        parser_class.assert_instantiated_with(data_model=data_model,
                                              version=version)
        parser.parse.assert_called_once_with()

        self.table.assert_called_with('metric_defaults', merge_update=True)
        table = self.table.return_value
        table.extend.assert_called_once_with([])
        table.write.assert_called_once_with(Path('export/TEST'))

class MetricOptionsCollectorTest(CollectorTest):
    """
    Tests for collector that retrieves changes to metric targets.
    """

    def test_collect(self) -> None:
        """
        Test collecting data from the project definition source.
        """

        version = {'version_id': '24680'}
        parser_class = mock_parser_class(Definition_Parser)
        parser = parser_class.return_value
        parser_attrs: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            'parse.return_value': {'24680': []}
        }
        parser.configure_mock(**parser_attrs)
        attrs = {
            'get_versions.return_value': [version],
            'parsers': {'metric_targets': parser_class}
        }
        data = self.data.return_value
        data.configure_mock(**attrs)

        with patch.object(Metric_Difference, 'export') as export:
            with patch('gatherer.project_definition.collector.Path',
                       autospec=True) as path_class:
                path_attrs = {
                    'exists.return_value': False,
                    'open.side_effect': FileNotFoundError
                }
                path = path_class.return_value
                path.configure_mock(**path_attrs)

                collector = Metric_Options_Collector(self.project, self.source)
                collector.collect()

                export.assert_called_once_with()

                path_class.assert_called_once_with(Path('export/TEST'),
                                                   'metric_names.json')
                path.open.assert_called_with('w', encoding='utf-8')
