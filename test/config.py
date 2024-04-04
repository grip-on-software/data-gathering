"""
Tests for configuration provider.

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
from gatherer.config import Configuration

class ConfigurationTest(unittest.TestCase):
    """
    Tests for access to options and sections of configuration files.
    """

    def setUp(self) -> None:
        Configuration.clear()

    def tearDown(self) -> None:
        Configuration.clear()

    def test_get_filename(self) -> None:
        """
        Test retrieving the file name for configuration.
        """

        self.assertEqual(Configuration.get_filename('settings'),
                                                    'settings.cfg.example')
        self.assertEqual(Configuration.get_filename('credentials'),
                                                    'credentials.cfg.example')
        self.assertEqual(Configuration.get_filename('custom'), 'custom.cfg')

    def test_get_config(self) -> None:
        """
        Test creating a configuration object loaded with options from a file.
        """

        config = Configuration.get_config('settings')
        self.assertEqual(config.get('jira', 'server'), '$JIRA_SERVER')

    def test_get_settings(self) -> None:
        """
        Test retrieving the settings configuration object.
        """

        settings = Configuration.get_settings()
        self.assertEqual(settings.get('jira', 'username'), '$JIRA_USER')
        # Calling the class method again provides the same object.
        self.assertIs(settings, Configuration.get_settings())

    def test_get_credentials(self) -> None:
        """
        Test retrieving the credentials configuration object.
        """

        credentials = Configuration.get_credentials()
        self.assertEqual(credentials.get('$SOURCE_HOST', 'env'),
                         '$SOURCE_CREDENTIALS_ENV')
        # Calling the class method again provides the same object.
        self.assertIs(credentials, Configuration.get_credentials())

    def test_has_value(self) -> None:
        """
        Test checking whether a value is not set to a falsy value.
        """

        for falsy in ('false', 'no', 'off', '-', '0', '', None):
            self.assertFalse(Configuration.has_value(falsy))
        for truthy in ('true', 'yes', 'on', 'a', '1'):
            self.assertTrue(Configuration.has_value(truthy))

    def test_get_agent_key(self) -> None:
        """
        Test retrieving the agent's primary project key.
        """

        self.assertEqual(Configuration.get_agent_key(), '$JIRA_KEY')

    def test_get_url_blacklist(self) -> None:
        """
        Test retrieving a regular expression for matching URLs that are known
        to be inaccessible.
        """

        pattern = Configuration.get_url_blacklist()
        self.assertFalse(pattern.match('http://example.test'))

        # Calling the class method again provides the same object.
        self.assertIs(Configuration.get_url_blacklist(), pattern)

    def test_is_url_blacklisted(self) -> None:
        """
        Test checking whether URLs should not be requested because they are
        known to be inaccessible.
        """

        with patch.dict('os.environ', {
                'GATHERER_URL_BLACKLIST': 'http://*.network,http://slow.test'
            }):
            for url in ('http://firewalled.network', 'http://slow.test/path/'):
                self.assertTrue(Configuration.is_url_blacklisted(url))
            self.assertFalse(Configuration.is_url_blacklisted('http://ok.test'))
