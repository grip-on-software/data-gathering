"""
Tests for Jenkins build system source domain object.

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
from gatherer.domain.source import Source, Jenkins

class JenkinsTest(unittest.TestCase):
    """
    Tests for Jenkins source.
    """

    def setUp(self) -> None:
        self.source = Source.from_type('jenkins', name='test-jenkins',
                                       url='https://jenkins.test/')

    def test_environment(self) -> None:
        """
        Test retrieving an indicator of the environment of the source.
        """

        self.assertEqual(self.source.environment, 'https://jenkins.test/')

    def test_environment_url(self) -> None:
        """
        Test retrieving an URL for the environment that the source lives in.
        """

        self.assertEqual(self.source.environment_url, 'https://jenkins.test/')

    def test_update_identity(self) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        with self.assertRaises(RuntimeError):
            self.source.update_identity(Project('TEST'), 'my-public-key')

    @patch('gatherer.domain.source.jenkins.JenkinsAPI')
    def test_version(self, api: MagicMock) -> None:
        """
        Test retrieving relevant version information for this source.
        """

        api.side_effect = RuntimeError
        self.assertEqual(self.source.version, '')
        api.side_effect = None

        api.return_value.configure_mock(version='1.2.3')
        self.assertEqual(self.source.version, '1.2.3')

    @patch('gatherer.domain.source.jenkins.JenkinsAPI')
    def test_jenkins_api(self, api: MagicMock) -> None:
        """
        Test retrieving the Jenkins API object for this source.
        """

        if not isinstance(self.source, Jenkins): # pragma: no cover
            self.fail("Incorrect source")
            return

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'https://jenkins.test'}):
            with self.assertRaises(RuntimeError):
                self.assertIsNone(self.source.jenkins_api)

        Configuration.clear()

        self.assertEqual(self.source.jenkins_api, api.return_value)
        api.assert_called_once_with('https://jenkins.test/',
                                    username=None, password=None, verify=True)
        api.reset_mock()

        # Retrieving the property again provides the same instance and does
        # not perform another authentication.
        self.assertEqual(self.source.jenkins_api, api.return_value)
        api.assert_not_called()
