"""
Tests for source domain objects.

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
import unittest
from gatherer.config import Configuration
from gatherer.domain.project import Project
from gatherer.domain.source.types import Source, Source_Types, Source_Type_Error

@Source_Types.register('test')
@Source_Types.register('test-cb', lambda cls, name='', **data: 'test' in name)
class Example(Source):
    """
    Example source for tests.
    """

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None: # pragma: no cover
        raise RuntimeError('Example source')

class SourceTypesTest(unittest.TestCase):
    """
    Tests for holder of source type registrations.
    """

    def test_get_source(self) -> None:
        """
        Retrieving an object that represents a source with a certain type.
        """

        self.assertIsInstance(Source_Types.get_source('test', name='test'),
                              Example)
        self.assertIsInstance(Source_Types.get_source('test-cb', name='test-2'),
                              Example)
        with self.assertRaises(Source_Type_Error):
            self.assertNotIsInstance(Source_Types.get_source('test-cb',
                                                             name='something'),
                                     Example)

class SourceTest(unittest.TestCase):
    """
    Tests for source interface.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('test', name='t0', url='http://t0.test')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_from_type(self) -> None:
        """
        Test creating a a source object from its source type.
        """

        self.assertIsInstance(self.source, Example)
        self.assertIsInstance(Source.from_type('test-cb', name='test-example'),
                              Example)

    def test_url(self) -> None:
        """
        Test retrieve the final URL, after following host changes and including
        credentials where applicable.
        """

        self.assertEqual(self.source.url, 'http://t0.test')

        credentials = Configuration.get_credentials()
        credentials.add_section('t1.test')
        credentials.set('t1.test', 'username', 'testuser')
        credentials.set('t1.test', 'password', 'testpass')
        credentials.set('t1.test', 'port', '8080')

        self.assertEqual(Source.from_type('test', name='t1',
                                          url='http://t1.test/path').url,
                         'http://testuser:testpass@t1.test:8080/path')

        # Test options when converting HTTP to SSH
        credentials.add_section('t2.test')
        credentials.set('t2.test', 'username.ssh', 'sshuser')
        credentials.set('t2.test', 'env', 'CREDENTIALS_FILE')
        credentials.set('t2.test', 'strip', 'base')
        self.assertEqual(Source.from_type('test', name='t2',
                                          url='http://t2.test/base/rest').url,
                         'ssh://sshuser@t2.test/rest')

        # Test invalid SSH domains
        with self.assertRaises(ValueError):
            self.assertEqual(Source.from_type('test', name='invalid-ssh',
                                              url='ssh://-.invalid/a').url, '')

        # Test local paths
        self.assertEqual(Source.from_type('test', name='local',
                                          url='/my/local/path').url,
                         '/my/local/path')

        # Test invalid port specification cleanup
        self.assertEqual(Source.from_type('test', name='invalid-port',
                                          url='http://test.invalid:port/b').url,
                         'http://test.invalid/b')

        # Test path strip with leading slash
        credentials.add_section('lead.test')
        credentials.set('lead.test', 'username', 'user')
        credentials.set('lead.test', 'env', 'CREDENTIALS_FILE')
        credentials.set('lead.test', 'strip', '/foo')
        self.assertEqual(Source.from_type('test', name='empty',
                                          url='http://lead.test/foo/bar').url,
                         'ssh://user@lead.test/bar')

    def test_properties(self) -> None:
        """
        Test various properties of the Source interface.
        """

        self.assertEqual(self.source.plain_url, 'http://t0.test')
        self.assertIsNone(self.source.web_url)
        self.assertEqual(self.source.type, 'test')
        self.assertEqual(self.source.name, 't0')
        self.assertIsNone(self.source.environment)
        self.assertEqual(self.source.environment_type, 'test')
        self.assertIsNone(self.source.environment_url)
        self.assertEqual(self.source.path_name, 't0')
        self.assertIsNone(self.source.repository_class)
        self.assertIsNone(self.source.project_definition_class)
        self.assertEqual(self.source.version, '')

        self.assertTrue(self.source.check_credentials_environment())
        self.assertEqual(self.source.get_sources(), [self.source])
        data = {
            'type': 'test',
            'name': 't0',
            'url': 'http://t0.test'
        }
        self.assertEqual(self.source.export(), data)
        self.assertEqual(repr(self.source), repr(data))
        self.assertEqual(hash(self.source),
                         hash((data['name'], data['type'], data['url'])))

        source = Source.from_type('test', name='t0', url='http://t0.test')
        other = Source.from_type('test', name='other', url='http://other.test')
        self.assertTrue(self.source == source)
        self.assertFalse(self.source == other)
        self.assertFalse(self.source == data)
        self.assertFalse(self.source != source)
        self.assertTrue(self.source != other)
        self.assertTrue(self.source != data)

    def test_credentials_path(self) -> None:
        """
        Test retrieving a path to a credentials file.
        """

        self.assertIsNone(self.source.credentials_path)
        self.source.credentials_path = 'test/sample/credentials'
        self.assertEqual(self.source.credentials_path,
                         Path('test/sample/credentials'))
        self.source.credentials_path = None
        self.assertIsNone(self.source.credentials_path)
