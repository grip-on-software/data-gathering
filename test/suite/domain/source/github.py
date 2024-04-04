"""
Tests for GitHub source domain object.

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
from github.Repository import Repository
from github.Team import Team
from gatherer.config import Configuration
from gatherer.domain.source import Source, GitHub

class GitHubTest(unittest.TestCase):
    """
    Tests for GitHub source repository.
    """

    def setUp(self) -> None:
        Configuration.clear()
        patcher = patch('github.Github', autospec=True)
        self.main_class = patcher.start()
        self.api = self.main_class.return_value
        self.addCleanup(patcher.stop)
        self.source = Source.from_type('github', name='test-git',
                                       url='git@github.test:owner/repo.git')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_is_github_url(self) -> None:
        """
        Test checking whether a given URL is part of a GitHub instance.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('token-github.test')
        credentials.set('token-github.test', 'github_token', 'secret-token')
        self.assertTrue(GitHub.is_github_url('https://token-github.test/a/b'))

    def test_properties(self) -> None:
        """
        Test retrieving most properties of the GitHub source.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('prop-github.test')
        credentials.set('prop-github.test', 'github_token', 'secret-token')
        credentials.set('prop-github.test', 'github_api_url',
                        'https://api.prop-github.test')
        source = GitHub('github', name='prop',
                        url='https://prop-github.test/org/repo',
                        github_team='prop-team')
        self.assertEqual(source.environment,
                         ('prop-github.test', 'org', 'prop-team'))
        self.assertEqual(source.environment_url, 'https://prop-github.test/org')
        self.assertEqual(source.web_url, 'https://prop-github.test/org/repo')
        self.assertEqual(source.github_token, 'secret-token')
        self.assertEqual(source.github_owner, 'org')
        self.assertEqual(source.github_team, 'prop-team')

        self.assertEqual(source.github_api, self.api)
        self.assertEqual(source.github_api, self.api)
        self.main_class.assert_called_once()
        self.assertEqual(self.main_class.call_args.kwargs['auth'].token,
                         'secret-token')
        self.assertEqual(self.main_class.call_args.kwargs['base_url'],
                         'https://api.prop-github.test')
        self.assertEqual(self.main_class.call_args.kwargs['verify'], True)

    def test_github_repo(self) -> None:
        """
        Test retrieving the repository information from the GitHub API.
        """

        if not isinstance(self.source, GitHub):
            self.fail("Incorrect source")
            return

        self.assertEqual(self.source.github_repo,
                         self.api.get_repo.return_value)
        # Calling again provides the same data but no extra calls.
        self.assertEqual(self.source.github_repo,
                         self.api.get_repo.return_value)
        self.api.get_repo.assert_called_once_with('owner/repo')

    def test_get_sources(self) -> None:
        """
        Test retrieving information about additional data sources.
        """

        repo = MagicMock(spec_set=Repository, name='repo2',
                         clone_url='https://github.test/owner/repo2.git')
        attrs = {
            'get_repos.return_value': [repo]
        }
        self.api.get_user.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.get_sources(), [
            Source.from_type('github', name=repo.name, url=repo.clone_url)
        ])

        source = Source.from_type('github', name='team-github',
                                  url='https://team-github.test/org/base.git',
                                  github_team='t1')

        attrs = {'get_teams.return_value': []}
        self.api.get_organization.return_value.configure_mock(**attrs)
        with self.assertRaises(RuntimeError):
            source.get_sources()

        team = MagicMock(spec_set=Team, slug='t1')
        team_attrs = {'get_repos.return_value': [repo]}
        team.configure_mock(**team_attrs)
        attrs = {
            'get_teams.return_value': [
                MagicMock(sepc_set=Team, slug='t0'), team
            ]
        }
        self.api.get_organization.return_value.configure_mock(**attrs)
        self.assertEqual(source.get_sources(), [
            Source.from_type('github', name=repo.name, url=repo.clone_url,
                             github_team='t1')
        ])
