"""
Tests for Git source domain object.

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

class ControllerTest(unittest.TestCase):
    """
    Tests for agent controller source.
    """

    def setUp(self) -> None:
        self.source = Source.from_type('git', name='test-git',
                                       url='git@git.test:repo.git')

    def test_url(self) -> None:
        """
        Test retrieving the final URL with credentials.
        """

        # Despite internal transformations, the SCP-like URL is provided again
        self.assertEqual(self.source.url, 'git@git.test:repo.git')

        credentials = Configuration.get_credentials()
        credentials.add_section('auth-git.test')
        credentials.set('auth-git.test', 'username', 'git-user')
        credentials.set('auth-git.test', 'password', 'git-password')
        http_source = Source.from_type('git', name='auth-test-git-http',
                                       url='https://auth-git.test/repo.git/')
        self.assertEqual(http_source.url,
                         'https://git-user:git-password@auth-git.test/repo.git')

        # Reformatted (externally) as an SCP-like URL
        ssh_source = Source.from_type('git', name='auth-test-git-ssh',
                                       url='ssh://auth-git.test/repo.git')
        self.assertEqual(ssh_source.url,
                         'git-user@auth-git.test:repo.git')

        credentials.add_section('auth-git.test:2222')
        credentials.set('auth-git.test:2222', 'username', 'ssh-git-user')
        port_source = Source.from_type('git', name='auth-test-git-ssh-port',
                                       url='ssh://auth-git.test:2222/repo.git')
        self.assertEqual(port_source.url,
                         'ssh://ssh-git-user@auth-git.test:2222/repo.git')

    def test_path_name(self) -> None:
        """
        Test retrieving a path name identifier of the source.
        """

        self.assertEqual(self.source.path_name, 'repo')

        self.assertEqual(Source.from_type('git', name='no-path',
                                          url='git@git.test').path_name,
                         'no-path')

        source = Source.from_type('git', name='long-path',
                                  url='git@git.test:foo/bar/baz/')
        self.assertEqual(source.path_name, 'baz')

    def test_update_identity(self) -> None:
        """
        Test whether the source can be updated to accept a public key.
        """

        with self.assertRaises(RuntimeError):
            self.source.update_identity(Project('TEST'), 'my-public-key')
