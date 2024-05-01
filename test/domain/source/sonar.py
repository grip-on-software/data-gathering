"""
Tests for SonarQube source domain object.

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
    Tests for SonarQube source.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('sonar', name='test-sonarqube',
                                       url='https://sonarqube.test')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_environment_url(self) -> None:
        """
        Thest retrieving a URL for the environment that the source lives in.
        """

        self.assertEqual(self.source.environment, 'https://sonarqube.test/')
        self.assertEqual(self.source.environment_url, 'https://sonarqube.test/')

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

        request.get('https://sonarqube.test/api/server/version', text='1.2.3')
        self.assertEqual(self.source.version, '1.2.3')

        Configuration.clear()

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'https://deny-sonar.test'}):
            deny = Source.from_type('sonar', name='deny-sonarqube',
                                    url='https://deny-sonar.test/')

            self.assertEqual(deny.version, '')

        Configuration.clear()

        credentials = Configuration.get_credentials()
        credentials.add_section('error-sonar.test')
        credentials.set('error-sonar.test', 'verify', '/path/to/server.crt')

        request.get('https://error-sonar.test/api/server/version',
                    exc=ConnectError)
        error = Source.from_type('sonar', name='error-sonarqube',
                                 url='https://error-sonar.test/')
        self.assertEqual(error.version, '')
        request.reset_mock()
        self.assertEqual(error.version, '')
        self.assertFalse(request.called)
