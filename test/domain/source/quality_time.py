"""
Tests for Quality-time source domain object.

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

import unittest
from unittest.mock import patch
from requests.exceptions import ConnectionError as ConnectError
import requests_mock
from gatherer.config import Configuration
from gatherer.domain.project import Project
from gatherer.domain.source import Source

class SonarTest(unittest.TestCase):
    """
    Tests for Quality-time source.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('quality-time', name='test-qt',
                                       url='https://quality-time.test')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_environment_url(self) -> None:
        """
        Test retrieving a URL for the environment that the source lives in.
        """

        self.assertEqual(self.source.environment,
                         ('quality-time', 'https://quality-time.test'))
        self.assertEqual(self.source.environment_url, 'https://quality-time.test')

    def test_update_identity(self) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        with self.assertRaises(RuntimeError):
            self.source.update_identity(Project('TEST'), 'my-public-key')

    @requests_mock.Mocker()
    def test_version(self, request: requests_mock.Mocker) -> None:
        """
        Test retrieving relevant version information for the source.
        """

        request.get('https://quality-time.test/api/v3/server', json={'version': '1.2.3'})
        self.assertEqual(self.source.version, '1.2.3')

        Configuration.clear()

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'https://deny-qt.test'}):
            deny = Source.from_type('quality-time', name='deny-qt',
                                    url='https://deny-qt.test/')

            self.assertEqual(deny.version, '')

        Configuration.clear()

        credentials = Configuration.get_credentials()
        credentials.add_section('error-qt.test')
        credentials.set('error-qt.test', 'verify', '/path/to/server.crt')

        request.get('https://error-qt.test/api/v3/server',
                    exc=ConnectError)
        error = Source.from_type('quality-time', name='error-qt',
                                 url='https://error-qt.test/')
        self.assertEqual(error.version, '')
