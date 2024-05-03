"""
Tests for Jira issue tracker source domain object.

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
from unittest.mock import patch, MagicMock
from gatherer.config import Configuration
from gatherer.domain.project import Project
from gatherer.domain.source import Source, Jira

class JiraTest(unittest.TestCase):
    """
    Tests for Jira source.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('jira', name='test-jira',
                                       url='https://jira.test/')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_environment_url(self) -> None:
        """
        Test retrieve a URL for the environment that the source lives in.
        """

        self.assertEqual(self.source.environment, 'https://jira.test')
        self.assertEqual(self.source.environment_url, 'https://jira.test')

    def test_update_identity(self) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        with self.assertRaises(RuntimeError):
            self.source.update_identity(Project('TEST'), 'my-public-key')

    @patch('gatherer.domain.source.jira.JIRA')
    def test_version(self, api: MagicMock) -> None:
        """
        Test retrieving relevant version information for the Jira source.
        """

        api.side_effect = RuntimeError
        self.assertEqual(self.source.version, '')
        api.side_effect = None

        source = Source.from_type('jira', name='good-jira',
                                  url='https://good-jira.test')
        attrs = {'server_info.return_value': {'version': '1.2.3'}}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(source.version, '1.2.3')
        api.return_value.server_info.assert_called_once_with()

        # The version is not requested again.
        self.assertEqual(source.version, '1.2.3')
        api.return_value.server_info.assert_called_once_with()

    def test_jira_agile_path(self) -> None:
        """
        Test retrieving the REST path to use for JIRA Agile requests.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('agile-jira.test')
        credentials.set('agile-jira.test', 'agile_rest_path', '/api/example/')

        source = Source.from_type('jira', name='agile-jira',
                                  url='https://agile-jira.test/')
        if not isinstance(source, Jira): # pragma: no cover
            self.fail("Incorrect source")

        self.assertEqual(source.jira_agile_path, '/api/example/')

    @patch('gatherer.domain.source.jira.JIRA')
    def test_jira_api(self, api: MagicMock) -> None:
        """
        Test retrieving the JIRA API object for this source.
        """

        if not isinstance(self.source, Jira): # pragma: no cover
            self.fail("Incorrect source")

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'https://jira.test'}):
            with self.assertRaises(RuntimeError):
                self.assertIsNone(self.source.jira_api)

        Configuration.clear()

        self.assertEqual(self.source.jira_api, api.return_value)
        api.reset_mock()

        # Retrieving the property again provides the same instance and does
        # not perform another authentication.
        self.assertEqual(self.source.jira_api, api.return_value)
        api.assert_not_called()

        credentials = Configuration.get_credentials()
        credentials.add_section('api-jira.test')
        credentials.set('api-jira.test', 'agile_rest_path', '/api/agile/')
        credentials.set('api-jira.test', 'username', 'jirauser')
        credentials.set('api-jira.test', 'password', 'jirapass')

        source = Source.from_type('jira', name='api-jira',
                                  url='https://api-jira.test/')
        if not isinstance(source, Jira): # pragma: no cover
            self.fail("Incorrect source")

        self.assertEqual(source.jira_api, api.return_value)
        api.assert_called_once_with(server='https://api-jira.test', options={
            'agile_rest_path': '/api/agile/',
            'verify': True
        }, basic_auth=('jirauser', 'jirapass'), max_retries=0)
