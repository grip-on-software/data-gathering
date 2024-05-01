"""
Tests for Subversion source domain object.

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
from gatherer.config import Configuration
from gatherer.domain.project import Project
from gatherer.domain.source import Source

class SubversionTest(unittest.TestCase):
    """
    Tests for Subversion repository source.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('subversion', name='test-subversion',
                                       url='https://svn.test/repo/trunk')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_url(self) -> None:
        """
        Test retrieving the final URL.
        """

        self.assertEqual(self.source.url, 'https://svn.test/repo')

        credentials = Configuration.get_credentials()
        credentials.add_section('env-svn.test')
        credentials.set('env-svn.test', 'env', 'CREDENTIALS_FILE')
        credentials.set('env-svn.test', 'username', 'svn-user')
        source = Source.from_type('subversion', name='test-subversion-env',
                                  url='https://env-svn.test/foo/bar')
        self.assertEqual(source.url, 'svn+ssh://svn-user@env-svn.test/foo/bar')

    def test_update_identity(self) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        with self.assertRaises(RuntimeError):
            self.source.update_identity(Project('TEST'), 'my-public-key')
