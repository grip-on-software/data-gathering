"""
Tests for interacting with multiple version control systems.

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

from itertools import chain, repeat
from pathlib import Path
from typing import Dict, Optional, Tuple, Type, Union
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from gatherer.domain.project import Project
from gatherer.domain.source import Source
from gatherer.table import Table
from gatherer.version_control.holder import Repositories_Holder, Tables
from gatherer.version_control.repo import PathLike, RepositorySourceException, \
    Version_Control_Repository

FileSpec = Union[str, bool]
RepositoryMockAttributes = Dict[str, Union[Tuple[str, ...], Optional[str], bool,
                                           Type[RepositorySourceException],
                                           Dict[str, str], Dict[str, Table]]]

class RepositoriesHolderTest(unittest.TestCase):
    """
    Tests for interacting with multiple version control systems..
    """

    def setUp(self) -> None:
        self.path_files: Dict[str, FileSpec] = {}
        self.paths: Dict[str, Union[Path, MagicMock]] = {}

        path_patcher = patch('gatherer.version_control.holder.Path',
                             autospec=True)
        self.path = path_patcher.start()
        self.path.configure_mock(side_effect=self._construct_path)
        self.addCleanup(path_patcher.stop)

        sprint_patcher = patch('gatherer.version_control.holder.Sprint_Data',
                               autospec=True)
        self.sprints = sprint_patcher.start().return_value
        self.addCleanup(sprint_patcher.stop)

        self.project = Project('TEST')
        self.holder = Repositories_Holder(self.project, 'repos')

        self.latest_path = Path('test/sample/latest_vcs_versions.json')
        self.latest_path.write_text('{"testrepo": "1234567890abcdef"}',
                                    encoding='utf-8')
        for tracker in ('vcs_test_tracker.json', 'vcs_extra.json'):
            Path('test/sample', tracker).write_text('{"testrepo": "data"}',
                                                    encoding='utf-8')

    def _construct_path(self, base: PathLike, name: str,
                        *args: str) -> Union[Path, MagicMock]:
        if name in self.paths:
            return self.paths[name]

        file = self.path_files.get(name)
        if file:
            if file is True:
                self.paths[name] = Path('test/sample', name)
            else:
                self.paths[name] = Path(file)
        else:
            path_mock = MagicMock(spec_set=Path, name='Path')(base, name, *args)
            if file is not None:
                attrs = {'exists.return_value': False}
                path_mock.configure_mock(**attrs)

            self.paths[name] = path_mock

        return self.paths[name]

    def _reset_path(self, name: Optional[str] = None,
                    file: Optional[FileSpec] = None) -> None:
        if name is not None:
            self.paths.pop(name, None)
            if file is not None:
                self.path_files[name] = file
        else:
            self.paths = {}

    def _get_path_mock(self, name: str) -> MagicMock:
        if name not in self.paths: # pragma: no cover
            raise KeyError(f'File {name} has not been called as a mock')

        path = self.paths[name]
        if not isinstance(path, MagicMock): # pragma: no cover
            raise ValueError(f'File {name} is not a mock')

        return path

    def test_load_latest_versions(self) -> None:
        """
        Test loading the information detailing the latest commits.
        """

        self._reset_path('latest_vcs_versions.json', True)
        self.assertEqual(self.holder.load_latest_versions(), {
            'testrepo': '1234567890abcdef'
        })

        self._reset_path('latest_vcs_versions.json', False)
        self.assertEqual(self.holder.load_latest_versions(), {})
        self._get_path_mock('latest_vcs_versions.json').open.assert_not_called()

    def test_get_repositories(self) -> None:
        """
        Test retrieving repositories for relevant version control systems.
        """

        tables: Tables = {}
        # No sources leads to no repositories.
        self.assertEqual(list(self.holder.get_repositories(tables)), [])

        # No sources with repository class leads to no repositories.
        self.project.sources.include(MagicMock(spec=Source,
                                               repository_class=None))
        self.assertEqual(list(self.holder.get_repositories(tables)), [])

        repo_class = MagicMock(spec=Version_Control_Repository,
                               AUXILIARY_TABLES=('test',),
                               UPDATE_TRACKER_NAME=None)
        repo = repo_class.from_source.return_value
        attrs: RepositoryMockAttributes = {'is_empty.return_value': True}
        repo.configure_mock(**attrs)
        self.project.sources.clear()
        source = MagicMock(spec=Source, repository_class=repo_class)
        source.configure_mock(name='testrepo')
        self.project.sources.include(source)
        self.assertEqual(list(self.holder.get_repositories(tables)), [])

        attrs = {'is_empty.return_value': False}
        repo.configure_mock(**attrs)
        self.assertEqual(list(self.holder.get_repositories(tables)), [repo])
        self.assertEqual(tables, {'test': []})

        self._reset_path('latest_vcs_versions.json', True)
        self.holder.load_latest_versions()
        attrs = {'is_up_to_date.return_value': False}
        repo_class.configure_mock(**attrs)
        self.assertEqual(list(self.holder.get_repositories(tables)), [repo])

        attrs = {'is_up_to_date.return_value': True}
        repo_class.configure_mock(**attrs)
        self.assertEqual(list(self.holder.get_repositories(tables)), [])

        attrs = {'is_up_to_date.side_effect': RepositorySourceException}
        repo_class.configure_mock(**attrs)
        self.assertEqual(list(self.holder.get_repositories(tables)), [repo])

        attrs = {
            'is_up_to_date.return_value': False,
            'from_source.side_effect': RepositorySourceException
        }
        repo_class.configure_mock(**attrs)
        self.assertEqual(list(self.holder.get_repositories(tables)), [])

        # Now perform update tracker loading.
        attrs = {
            'from_source.side_effect': None,
            'UPDATE_TRACKER_NAME': 'vcs_test_tracker'
        }
        repo_class.reset_mock()
        repo_class.configure_mock(**attrs)
        attrs = {
            'update_trackers': {
                'vcs_test_tracker': 'data',
                'missing_tracker': ''
            }
        }
        repo.configure_mock(**attrs)
        self._reset_path('vcs_test_tracker.json', True)
        self._reset_path('missing_tracker.json', False)
        self.assertEqual(list(self.holder.get_repositories(tables)), [repo])
        repo_class.is_up_to_date.assert_called_once_with(source,
                                                         '1234567890abcdef',
                                                         update_tracker='data')

        repo_class.reset_mock()
        self._reset_path('vcs_test_tracker.json', False)
        self.holder.clear_update_tracker('vcs_test_tracker')
        self.assertEqual(list(self.holder.get_repositories(tables)), [repo])
        repo_class.is_up_to_date.assert_called_once_with(source,
                                                         '1234567890abcdef',
                                                         update_tracker=None)

    @patch('gatherer.version_control.holder.Table', autospec=True)
    def test_process(self, table: MagicMock) -> None:
        """
        Test performing all actions required for retrieving updated commit data.
        """

        repo_class = MagicMock(spec=Version_Control_Repository,
                               AUXILIARY_TABLES=('test',),
                               UPDATE_TRACKER_NAME='vcs_test_tracker')
        class_attrs = {'is_up_to_date.return_value': False}
        repo_class.configure_mock(**class_attrs)
        self.project.sources.clear()
        source = MagicMock(spec=Source, repository_class=repo_class)
        source_attrs = {
            'name': 'testrepo',
            'get_option.return_value': False
        }
        source.configure_mock(**source_attrs)
        self.project.sources.include(source)

        repo = repo_class.from_source.return_value
        tracker_data = {'vcs_test_tracker': 'data', 'vcs_extra': '1234'}
        trackers = PropertyMock(side_effect=chain([{}], repeat(tracker_data)))
        repo_attrs: RepositoryMockAttributes = {
            'is_empty.return_value': False,
            'get_latest_version.return_value': '1234567890abcdef',
            'repo_name': 'testrepo',
            'source': source,
            'tables': {'test': Table('test'), 'extra': Table('extra')},
            'update_trackers': trackers
        }
        repo.configure_mock(**repo_attrs)

        self._reset_path('vcs_test_tracker.json', True)
        self._reset_path('latest_vcs_versions.json', True)
        self.holder.process()
        table.assert_called_once_with('vcs_versions',
                                      encrypt_fields=('developer',
                                                      'developer_username',
                                                      'developer_email'))
        versions = table.return_value
        repo.get_data.assert_called_once_with(from_revision='1234567890abcdef',
                                              force=False, stats=True)
        versions.extend.assert_called_once_with(repo.get_data.return_value)
        versions.write.assert_called_once_with(Path('export/TEST'))

        # A repository with problems leads to no rows being added to the table.
        versions.reset_mock()
        repo_attrs = {'get_data.side_effect': RepositorySourceException}
        repo.configure_mock(**repo_attrs)
        self.holder.process()
        versions.extend.assert_not_called()

        # Forcing an update on a repository with problems means the latest
        # version is removed, so that it might be processed properly next time.
        self.holder.process(force=True)
        self.assertEqual(self.latest_path.read_text(encoding='utf-8'), '{}')

        # A new process attempt retrieves data with no start revision.
        repo.reset_mock()
        versions.reset_mock()
        repo_attrs = {'get_data.side_effect': None}
        repo.configure_mock(**repo_attrs)
        self.holder.process(force=True)
        repo.get_data.assert_called_once_with(from_revision=None,
                                              force=True, stats=True)
        versions.extend.assert_called_once_with(repo.get_data.return_value)
