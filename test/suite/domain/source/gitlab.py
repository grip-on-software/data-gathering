"""
Tests for GitLab source domain object.

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

from typing import Any, Dict
import unittest
from unittest.mock import patch, MagicMock
from gitlab.exceptions import GitlabAuthenticationError
from requests.exceptions import ConnectionError as ConnectError
from gatherer.config import Configuration
from gatherer.domain.project import Project
from gatherer.domain.source import Source, GitLab

class GitLabTest(unittest.TestCase):
    """
    Tests for GitLab source repository.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('gitlab', name='test-gitlab',
                                       url='https://gitlab.test/group/repo')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_is_gitlab_url(self) -> None:
        """
        Test checking whether a URL is part of a GitLab instance.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('source.test')
        credentials.set('source.test', 'gitlab_token', 'secret-token')
        self.assertTrue(GitLab.is_gitlab_url('https://source.test/group/repo'))

        credentials.add_section('archived.test')
        credentials.set('archived.test', 'host', 'source.test')
        self.assertTrue(GitLab.is_gitlab_url('https://archived.test/org/repo'))
        self.assertFalse(GitLab.is_gitlab_url('https://archived.test/org/repo',
                                              follow_host_change=False))

    def test_url(self) -> None:
        """
        Test retrieving the final URL after applying credentials.
        """

        self.assertEqual(self.source.url, 'https://gitlab.test/group/repo')

        credentials = Configuration.get_credentials()
        credentials.add_section('redirect.test')
        credentials.set('redirect.test', 'host', 'strip.test')
        credentials.add_section('strip.test')
        credentials.set('strip.test', 'strip', 'prefix')
        strip_http = Source.from_type('gitlab', name='strip-gitlab-http',
                                      url='https://redirect.test/nested/repo')
        self.assertEqual(strip_http.url, 'https://strip.test/nested/repo')

        # Now actually test the strip option with HTTPS to SSH conversion
        credentials.set('strip.test', 'env', 'CREDENTIALS_FILE')
        strip_ssh = Source.from_type('gitlab', name='strip-gitlab-to-ssh',
                                     url='https://redirect.test/prefix/a/b.git')
        self.assertEqual(strip_ssh.url, 'strip.test:a/b.git')
        # Prefix and original protocol are preserved in environment URL
        self.assertEqual(strip_ssh.environment_url,
                         'https://strip.test/prefix/a')

        # Test updating paths at redirected site with gitlab group option
        credentials.set('redirect.test', 'group', 'g1')
        credentials.set('strip.test', 'username', 'git-user')
        group = Source.from_type('gitlab', name='group-gitlab-g1',
                                 url='https://redirect.test/owner/base.git/')
        self.assertEqual(group.url, 'git-user@strip.test:g1/owner-base.git')

        credentials.remove_option('strip.test', 'env')
        namespace = Source.from_type('gitlab', name='group-gitlab-ns',
                                     url='https://redirect.test/org/common')
        self.assertEqual(namespace.url, 'https://strip.test/g1/org-common')

        credentials.set('strip.test', 'password', 'pw')
        ns_pass = Source.from_type('gitlab', name='group-gitlab-ns-pass',
                                   url='https://redirect.test/g1/grepo')
        self.assertEqual(ns_pass.url, 'https://git-user:pw@strip.test/g1/grepo')

    def test_properties(self) -> None:
        """
        Test retrieving most properties of the GitLab source.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('prop.test')
        credentials.set('prop.test', 'gitlab_token', 'secret-token')
        credentials.set('prop.test', 'group', 'g1')

        source = GitLab('gitlab', name='prop',
                        url='https://prop.test/owner/repo')

        self.assertEqual(source.environment,
                         ('https://prop.test', 'g1', 'owner'))
        self.assertEqual(source.environment_url, 'https://prop.test/g1')
        self.assertEqual(source.web_url, 'https://prop.test/owner/repo')
        self.assertEqual(source.host, 'https://prop.test')
        self.assertEqual(source.gitlab_token, 'secret-token')
        self.assertEqual(source.gitlab_group, 'g1')
        self.assertEqual(source.gitlab_namespace, 'owner')
        self.assertEqual(source.gitlab_path, 'owner%2Frepo')

    @patch('gatherer.domain.source.gitlab.Gitlab')
    def test_version(self, api: MagicMock) -> None:
        """
        Test retrieving the version information of Gitlab.
        """

        api.side_effect = RuntimeError
        self.assertEqual(self.source.version, '')
        api.side_effect = None

        attrs: Dict[str, Any] = {'version.return_value': ['unknown']}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.version, '')

        attrs = {'version.return_value': ['1.2.3', 'dev']}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.version, '1.2.3')

        attrs = {'version.side_effect': RuntimeError}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.version, '')

    @patch('gatherer.domain.source.gitlab.Gitlab')
    def test_gitlab_api(self, api: MagicMock) -> None:
        """
        Test retrieving an instance of the GitLab API connection.
        """

        if not isinstance(self.source, GitLab):
            self.fail("Incorrect source")
            return

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'https://gitlab.test'}):
            with self.assertRaises(RuntimeError):
                self.assertIsNone(self.source.gitlab_api)

        Configuration.clear()

        api.side_effect = ConnectError
        with self.assertRaises(RuntimeError):
            self.assertIsNone(self.source.gitlab_api)
        api.side_effect = None

        self.assertEqual(self.source.gitlab_api, api.return_value)
        api.return_value.auth.assert_called_once_with()

        # Retrieving the property again provides the same instance and does
        # not perform another authentication.
        self.assertEqual(self.source.gitlab_api, api.return_value)
        api.return_value.auth.assert_called_once_with()

    def test_check_credentials(self) -> None:
        """
        Test checking whether the source environment is within the credentials.
        """

        self.assertTrue(self.source.check_credentials_environment())

        credentials = Configuration.get_credentials()
        credentials.add_section('group.test')
        credentials.set('group.test', 'gitlab_token', 'secret-token')
        credentials.set('group.test', 'group', 'g1')

        source = Source.from_type('gitlab', name='group',
                                  url='https://group.test/owner/repo')
        self.assertFalse(source.check_credentials_environment())

    @patch('gatherer.domain.source.gitlab.Gitlab')
    def test_get_sources(self, api: MagicMock) -> None:
        """
        Test retrieving information about additional data sources.
        """

        attrs = {'get.side_effect': GitlabAuthenticationError}
        api.return_value.groups.configure_mock(**attrs)
        self.assertEqual(self.source.get_sources(), [self.source])

    @patch('gatherer.domain.source.gitlab.Gitlab')
    def test_update_identity(self, api: MagicMock) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        project = Project('TEST')
        with self.assertRaises(RuntimeError):
            self.source.update_identity(project, 'my-public-key')

        credentials = Configuration.get_credentials()
        credentials.add_section('key.test')
        credentials.set('key.test', 'gitlab_token', 'secret-token')
        source = Source.from_type('gitlab', name='gitlab-key-test',
                                  url='https://key.test/some/repo')

        title = 'GROS agent for the TEST project'
        other = MagicMock(key='other-public-key', title='unrelated')
        old = MagicMock(key='old-public-key', title=title)
        attrs = {'list.return_value': [other, old]}
        keys = api.return_value.user.keys
        keys.configure_mock(**attrs)

        source.update_identity(project, 'my-public-key', dry_run=True)
        old.delete.assert_not_called()
        keys.create.assert_not_called()

        source.update_identity(project, 'my-public-key')
        other.delete.assert_not_called()
        old.delete.assert_called_once_with()
        keys.create.assert_called_once_with({
            'title': title,
            'key': 'my-public-key'
        })

        same = MagicMock(key='my-public-key', title=title)
        attrs = {'list.return_value': [same]}
        keys = api.return_value.user.keys
        keys.configure_mock(**attrs)
        keys.create.reset_mock()

        source.update_identity(project, 'my-public-key')
        same.delete.assert_not_called()
        keys.create.assert_not_called()
