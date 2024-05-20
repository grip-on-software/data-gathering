"""
Tests for collections of sources.

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
from typing import Dict, List
import unittest
from unittest.mock import patch, MagicMock
from gatherer.domain.source import Source, Controller
from gatherer.domain.sources import Sources

class SourcesTest(unittest.TestCase):
    """
    Test for collection of sources related to a project.
    """

    def setUp(self) -> None:
        self.sources = Sources()

    def test_load_file(self) -> None:
        """
        Test importing a JSON file containing source dictionaries.
        """

        sources_path = Path('test/sample/data_sources.json')
        self.sources.load_file(sources_path)
        with sources_path.open('r', encoding='utf-8') as sources_file:
            sources: List[Dict[str, str]] = json.load(sources_file)
            source_types = set()
            for source_data in sources:
                source_type = source_data.pop('type')
                source_types.add(source_type)
                self.assertIn(Source.from_type(source_type,
                                               name=source_data['name'],
                                               url=source_data['url']),
                              self.sources)
            for source in self.sources:
                self.assertIn(source.type, source_types)
            self.assertEqual(len(self.sources), len(sources))

        self.sources.clear()
        self.sources.load_file(Path('test/sample/invalid_sources.json'))
        self.assertEqual(len(self.sources), 0)

    def test_load_sources(self) -> None:
        """
        Test importing source dictionaries into the collection.
        """

        source_data = [
            {
                "type": "subversion",
                "name": "Trunk",
                "url": "http://svn.test/repo/trunk"
            }
        ]
        source = Source.from_type('subversion', name='Trunk',
                                  url='http://svn.test/repo/trunk')

        self.sources.load_sources(source_data)
        self.assertIn(source, self.sources)
        self.assertIn(source_data[0], self.sources)
        self.assertEqual(len(self.sources), 1)

        # Another way to import sources from the set constructor signature.
        sources = Sources(source_data)
        self.assertIn(source, sources)
        self.assertEqual(sources, self.sources)

        # Sources are also constructable using set operations.
        union = Sources() | sources
        self.assertIn(source, union)
        self.assertEqual(union, sources)

        # Sources can also be mutated in set operations.
        sources -= union
        self.assertNotIn(source, sources)
        self.assertEqual(len(sources), 0)

    def test_get(self) -> None:
        """
        Test retrieving all sources in the collection.
        """

        self.assertEqual(self.sources.get(), set())
        self.sources.load_file(Path('test/sample/data_sources.json'))
        self.assertNotEqual(self.sources.get(), set())

    def test_include(self) -> None:
        """
        Test adding a new source to the collection.
        """

        controller = Source.from_type('controller', name='Central',
                                      url='https://central.test/auth')
        self.assertNotIn(controller, self.sources)
        self.sources.include(controller)
        self.assertIn(controller, self.sources)
        self.sources.include(controller)
        self.assertEqual(len(self.sources), 1)

    def test_delete(self) -> None:
        """
        Test removing an existing source.
        """

        controller = Source.from_type('controller', name='Controller',
                                      url='https://central.test/auth')
        with self.assertRaises(KeyError):
            self.sources.delete(controller)

        self.sources.include(controller)
        self.sources.delete(controller)
        self.assertNotIn(controller, self.sources)

        # Again, but with a different source that looks a lot like it
        similar = Source.from_type('controller', name='Related',
                                   url='https://central.test/auth')
        self.sources.include(similar)
        with self.assertRaises(KeyError):
            self.sources.delete(controller)

        self.sources.include(controller)
        self.sources.delete(controller)
        self.assertNotIn(controller, self.sources)
        self.assertIn(similar, self.sources)

        # Source with no environment specified
        svn = Source.from_type('subversion', name='Non-environmental',
                               url='http://svn.test/repo')
        self.sources.include(svn)
        self.sources.delete(svn)
        self.assertNotIn(svn, self.sources)

    def test_replace(self) -> None:
        """
        Test replacing an existing source with one with the same URL.
        """

        controller = Source.from_type('controller', name='Newer',
                                      url='https://central.test/auth')
        with self.assertRaises(KeyError):
            self.sources.replace(controller)
        self.sources.add(Source.from_type('controller', name='Original',
                                          url='https://central.test/auth'))
        self.sources.replace(controller)
        self.assertIn(controller, self.sources)

    def test_has_url(self) -> None:
        """
        Test checking whether there is a source with the same URL.
        """

        controller = Source.from_type('controller', name='Fresh',
                                      url='https://central.test/auth')
        other = Source.from_type('controller', name='Stale',
                                 url='https://central.test/auth')
        self.assertFalse(self.sources.has_url(controller.url))
        self.sources.add(other)
        self.assertTrue(self.sources.has_url(controller.url))

    def test_discard(self) -> None:
        """
        Test removing a source.
        """

        controller = Source.from_type('controller', name='Controller',
                                      url='https://central.test/auth')
        self.sources.discard(controller)
        self.sources.include(controller)
        self.sources.discard(controller)
        self.assertNotIn(controller, self.sources)

    def test_clear(self) -> None:
        """
        Test removing all sources.
        """

        self.sources.load_file(Path('test/sample/data_sources.json'))
        self.sources.clear()
        self.assertEqual(len(self.sources), 0)

    def test_get_environments(self) -> None:
        """
        Test yielding source objects that are distinctive for each environment.
        """

        one = Source.from_type('controller', name='First',
                               url='https://central.test/auth')
        two = Source.from_type('controller', name='Second',
                               url='https://central.test/auth')
        self.sources.include(one)
        self.sources.include(two)
        count = 0
        for environment in self.sources.get_environments():
            self.assertIn(environment, [one, two])
            count += 1
        self.assertEqual(count, 1)

    def test_find_source_type(self) -> None:
        """
        Test retrieving the first found source object for a specific type.
        """

        self.assertIsNone(self.sources.find_source_type(Controller))
        sources = [
            Source.from_type('jira', name='Board', url='https://jira.test'),
            Source.from_type('controller', name='Any',
                             url='https://central.test/auth')
        ]
        for source in sources:
            self.sources.include(source)
        self.assertEqual(self.sources.find_source_type(Controller), sources[1])

    def test_find_sources_by_type(self) -> None:
        """
        Test providing a generator with source objects for a specific type.
        """

        self.assertEqual(list(self.sources.find_sources_by_type(Controller)), [])
        sources = [
            Source.from_type('git', name='Repo', url='http://git.test/a/b.git'),
            Source.from_type('controller', name='Centralized',
                             url='https://central.test/auth'),
            Source.from_type('controller', name='Local',
                             url='https://controller.test/auth')
        ]
        for source in sources:
            self.sources.include(source)
        for generated in self.sources.find_sources_by_type(Controller):
            self.assertIn(generated, sources[1:])

    def test_export(self) -> None:
        """
        Test exporting a list of dictionaries of sources in the collection.
        """

        attrs = {'exists.return_value': False}
        path = MagicMock(spec=Path)
        path.configure_mock(**attrs)

        self.assertEqual(self.sources.export(), [])
        path.open.assert_not_called()
        sources_path = Path('test/sample/data_sources.json')
        self.sources.load_file(sources_path)
        with sources_path.open('r', encoding='utf-8') as sources_file:
            sources: List[Dict[str, str]] = json.load(sources_file)
            source_types = {source['type'] for source in sources}

        export_sources = self.sources.export()
        path.open.assert_not_called()
        for export_source in export_sources:
            self.assertIn(export_source['type'], source_types)
        self.assertEqual(len(export_sources), len(sources))

        # Now actually provide a path to write to
        exportable = Sources(path)
        exportable.export()
        path.open.assert_called_once()

    @patch('gatherer.domain.sources.Path', autospec=True)
    def test_export_environments(self, path: MagicMock) -> None:
        """
        Test exporting a description of each environment.
        """

        self.sources.load_sources([
            {
                "type": "controller",
                "name": "Test",
                "url": "http://controller.test/auth"
            }
        ])
        self.sources.export_environments(path('test/sample/export_env.json'))
        path.return_value.open.assert_called_once()

    def test_repr(self) -> None:
        """
        Test retrieving a string representation of the collection.
        """

        self.assertEqual(repr(self.sources), 'Sources(set())')
        self.sources.load_file(Path('test/sample/data_sources.json'))
        self.assertNotEqual(repr(self.sources), 'Sources(set())')
