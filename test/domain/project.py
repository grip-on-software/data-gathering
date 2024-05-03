"""
Tests for project domain objects.

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
from unittest.mock import patch, MagicMock
from gatherer.config import Configuration
from gatherer.domain.project import Project_Meta, Project
from gatherer.domain.source import Source

class ProjectMetaTest(unittest.TestCase):
    """
    Tests for class that holds information that may span multiple projects.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.project_meta = Project_Meta()

    def tearDown(self) -> None:
        Configuration.clear()

    def test_get_key_setting(self) -> None:
        """
        Test retrieving a configuration setting.
        """

        self.assertEqual(self.project_meta.get_key_setting('jira', 'server'),
                         '$JIRA_SERVER')
        with self.assertRaises(KeyError):
            self.project_meta.get_key_setting('invalid-section', 'server')
        with self.assertRaises(KeyError):
            self.project_meta.get_key_setting('jira', 'invalid-option')

        # Formatter arguments
        self.assertEqual(self.project_meta.get_key_setting('definitions',
                                                           'path', 'Test'),
                         '$DEFINITIONS_PATH/Test')

    def test_settings(self) -> None:
        """
        Test retrieving the settings.
        """

        settings = self.project_meta.settings
        self.assertEqual(settings.get('jira', 'username'), '$JIRA_USER')
        # Calling the property again, even on a different object, provides the
        # same object.
        self.assertIs(settings, Project_Meta().settings)

    @patch('gatherer.domain.project.Source.from_type')
    def test_make_project_definitions(self, source: MagicMock) -> None:
        """
        Test creating a project definitions source object.
        """

        self.project_meta.make_project_definitions(section='quality-time',
                                                   project_name=None)
        source.assert_called_once_with('quality-time',
                                       name='$QUALITY_TIME_NAME',
                                       url='$QUALITY_TIME_URL')
        source.reset_mock()

        settings = self.project_meta.settings
        settings.set('quality-time', 'url', '$QUALITY_TIME_URL/{}')
        self.project_meta.make_project_definitions(section='quality-time',
                                                   project_name='test')
        source.assert_called_once_with('quality-time',
                                       name='$QUALITY_TIME_NAME',
                                       url='$QUALITY_TIME_URL/test')

class ProjectTest(unittest.TestCase):
    """
    Tests for object that holds information about a project.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.project = Project('TEST')

    def tearDown(self) -> None:
        Configuration.clear()
        self.project.sources.clear()

    def test_get_group_setting(self) -> None:
        """
        Test retrieving a project setting from a configuration section.
        """

        self.assertIsNone(self.project.get_group_setting('projects'))

        project = Project('$JIRA_KEY')
        self.assertEqual(project.settings.options('support'), ['$jira_key'])
        self.assertEqual(project.get_group_setting('support'), '$SUPPORT_TEAM')

    def test_get_key_setting(self) -> None:
        """
        Test retrieving a configuration setting.
        """

        # Normal behavior from project meta is preserved for usual keys.
        self.assertEqual(self.project.get_key_setting('jira', 'server'),
                         '$JIRA_SERVER')

        # Create a setting for the project and obtain it when requested.
        self.project.settings.set('quality-time', 'url.TEST',
                                  'http://quality-time.test')
        self.assertEqual(self.project.get_key_setting('quality-time', 'url'),
                         'http://quality-time.test')
        self.assertEqual(self.project.get_key_setting('quality-time', 'url',
                                                      project=False),
                         '$QUALITY_TIME_URL')

    def test_has_source(self) -> None:
        """
        Test checking whether the project has a source.
        """

        source = Source('test-type', 'test', 'http://example.test')
        self.assertFalse(self.project.has_source(source))
        self.project.sources.add(source)
        self.assertTrue(self.project.has_source(source))
        self.assertTrue(self.project.has_source(Source('test-type', 'test2',
                                                       'http://example.test')))

    @patch('gatherer.domain.project.Path', autospec=True)
    def test_make_export_directory(self, path: MagicMock) -> None:
        """
        Test ensuring that the export directory exists.
        """

        attrs = {'exists.return_value': False}
        path.return_value.configure_mock(**attrs)
        self.project.make_export_directory()
        path.return_value.mkdir.assert_called_once_with(parents=True)

        path.return_value.reset_mock()
        attrs = {'exists.return_value': True}
        path.return_value.configure_mock(**attrs)
        self.project.make_export_directory()
        path.return_value.mkdir.assert_not_called()

    @patch('gatherer.domain.project.Path', autospec=True)
    def test_export_sources(self, path: MagicMock) -> None:
        """
        Test exporting data about registered sources.
        """

        attrs = {
            'exists.return_value': False,
            '__truediv__.return_value': path.return_value
        }
        path.return_value.configure_mock(**attrs)
        project = Project('TEST')
        project.export_sources()
        self.assertEqual(path.return_value.open.call_count, 2)

    def test_export_key(self) -> None:
        """
        Test retrieving the directory path used for project data exports.
        """

        self.assertEqual(self.project.export_key, Path('export/TEST'))

    def test_update_key(self) -> None:
        """
        Test retrieving the directory path used for obtaining update trackers.
        """

        self.assertEqual(self.project.update_key, Path('update/TEST'))

    def test_dropins_key(self) -> None:
        """
        Test retrieving the directory path where dropins may be found.
        """

        self.assertEqual(self.project.dropins_key, Path('dropins/TEST'))

    def test_github_team(self) -> None:
        """
        Test retrieving the GitHub team slug.
        """

        self.assertIsNone(self.project.github_team)

        project = Project('$JIRA_KEY')
        project.sources.add(Source.from_type('github', name='test-github',
                                             url='https://github.com'))
        self.assertEqual(project.github_team, '$TEAM_NAME')

    def test_gitlab_group_name(self) -> None:
        """
        Test retrieving the name used for a GitLab group.
        """

        self.assertIsNone(self.project.gitlab_group_name)
        self.project.sources.add(Source.from_type('gitlab', name='test-gitlab',
                                                  url='https://gitlab.com'))
        # No GitLab group name in credentials and no project name setting
        self.assertIsNone(self.project.gitlab_group_name)

        project = Project('$JIRA_KEY')
        project.sources.add(Source.from_type('gitlab', name='test2',
                                             url='http://gitlab.example/path'))
        # No GitLab group name in credentials, so project name setting is used
        self.assertEqual(project.gitlab_group_name, '$PROJECT_NAME')

        credentials = Configuration.get_credentials()
        credentials.add_section('gitlab.test')
        credentials.set('gitlab.test', 'group', 'testgroup')
        self.project.sources.clear()
        self.project.sources.add(Source.from_type('gitlab', name='test-gitlab',
                                                  url='http://gitlab.test'))
        # GitLab group name in credentials
        self.assertEqual(self.project.gitlab_group_name, 'testgroup')

    def test_tfs_collection(self) -> None:
        """
        Test retrieving the path used for a TFS collection.
        """

        self.assertIsNone(self.project.tfs_collection)

        credentials = Configuration.get_credentials()
        credentials.add_section('azure.test')
        credentials.set('azure.test', 'username', 'foo')
        credentials.set('azure.test', 'password', 'bar')
        self.project.sources.add(Source.from_type('tfs', name='test-tfs',
                                                  url='https://azure.test'))
        # No TFS collection in URL, so fall back to project key
        self.assertEqual(self.project.tfs_collection, 'TEST')

        self.project.sources.clear()
        self.project.sources.add(Source.from_type('tfs', name='test-tfs2',
                                                  url='http://azure.test/baz/'))
        self.assertEqual(self.project.tfs_collection, 'baz')

    def test_quality_metrics_name(self) -> None:
        """
        Test retrieving the name used in the quality metrics project definition.
        """

        self.assertIsNone(self.project.quality_metrics_name)
        project = Project('$JIRA_KEY')
        self.assertEqual(project.quality_metrics_name, '$PROJECT_NAME')
        subproject = Project('$SUBPROJECT_KEY')
        self.assertIsNone(subproject.quality_metrics_name)

    def test_main_project(self) -> None:
        """
        Test retrieving the main project.
        """

        self.assertIsNone(self.project.main_project)
        subproject = Project('$SUBPROJECT_KEY')
        self.assertEqual(subproject.main_project, '$JIRA_KEY')

    def test_project_definitions(self) -> None:
        """
        Test reetrieving a set of sources that describe where to find the
        project definitions.
        """

        self.assertEqual(self.project.project_definitions_sources, set())

        project = Project('$JIRA_KEY')
        self.assertEqual(project.project_definitions_sources, {
            Source.from_type('quality-time', name='$QUALITY_TIME_NAME',
                             url='$QUALITY_TIME_URL')
        })
