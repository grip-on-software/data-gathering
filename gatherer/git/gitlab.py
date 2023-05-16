"""
Module that handles access to a GitLab-based repository, augmenting the usual
repository version information with merge requests and commit comments.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, cast, TYPE_CHECKING
from git import Commit, GitCommandError
import gitlab.v4.objects
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError
from .repo import Git_Repository, RepositorySourceException
from ..table import Table, Key_Table
from ..utils import get_local_datetime, parse_utc_date, parse_unicode
from ..version_control.repo import Version_Control_Repository, PathLike, Version
from ..version_control.review import Review_System
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
    from ..domain.source import GitLab
else:
    Project = object
    Source = object
    GitLab = object

class GitLab_Dropins_Parser:
    """
    Parser for dropins containing an exported version of GitLab API responses.
    """

    def __init__(self, repo: Version_Control_Repository, filename: Path) -> None:
        self._repo = repo
        self._filename = filename

    @property
    def repo(self) -> Version_Control_Repository:
        """
        Retrieve the repository that this dropin parser feeds.
        """

        return self._repo

    @property
    def filename(self) -> Path:
        """
        Retrieve the path to the dropin file that is parsed.
        """

        return self._filename

    def parse(self) -> bool:
        """
        Check whether the dropin file can be found and parse it if so.

        Returns a boolean indicating if any data for the repository could be
        retrieved.
        """

        logging.info('Repository %s: Checking dropin file %s',
                     self.repo.repo_name, self._filename)
        if not self._filename.exists():
            logging.info('Dropin file %s does not exist', self._filename)
            return False

        with self._filename.open('r', encoding='utf-8') as dropin_file:
            data: List[Dict[str, str]] = json.load(dropin_file)

        return self._parse(data)

    def _parse(self, data: List[Dict[str, str]]) -> bool:
        raise NotImplementedError('Must be implemented by subclasses')

class GitLab_Table_Dropins_Parser(GitLab_Dropins_Parser):
    """
    Parser for dropins that contain a list of JSON objects, which may be
    relevant to the current repository.
    """

    def __init__(self, repo: Version_Control_Repository, filename: Path) -> None:
        super().__init__(repo, filename)

        self._table: Optional[Table] = None
        basename = self.filename.name
        if basename.startswith('data_') and basename.endswith('.json'):
            table_name = basename[len('data_'):-len('.json')]
            tables = self.repo.tables
            if table_name in tables:
                self._table = tables[table_name]

    def _parse(self, data: List[Dict[str, str]]) -> bool:
        if self._table is None:
            logging.warning('Could not deduce dropins table name from file %s',
                            self.filename)
            return False

        for value in data:
            if value['repo_name'] == self.repo.repo_name:
                self._table.append(value)

        return True

class GitLab_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by a GitLab instance.
    """

    UPDATE_TRACKER_NAME = 'gitlab_update'

    ISO8601_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

    AUXILIARY_TABLES = Git_Repository.AUXILIARY_TABLES | \
        Review_System.AUXILIARY_TABLES | {'gitlab_repo', 'vcs_event'}

    def __init__(self, source: Source, repo_directory: PathLike,
                 project: Optional[Project] = None, **kwargs: Any) -> None:
        super().__init__(source, repo_directory, project=project, **kwargs)
        self._repo_project: Optional[gitlab.v4.objects.Project] = None
        has_commit_comments = self._source.get_option('has_commit_comments')
        self._has_commit_comments = has_commit_comments is not None

        # List of dropin files that contain table data for GitLab only.
        self._table_dropin_files = [
            f'data_{table}.json' for table in self.review_tables
        ]

    @property
    def review_tables(self) -> Dict[str, Table]:
        review_tables = super().review_tables
        review_tables.update({
            "gitlab_repo": Key_Table('gitlab_repo', 'gitlab_id'),
            "vcs_event": Table('vcs_event',
                               encrypt_fields=('user', 'username', 'email'))
        })
        return review_tables

    def _check_dropin_files(self, project: Optional[Project] = None) -> bool:
        if project is None:
            return False

        has_dropins = False
        has_table_dropins = False
        for table_dropin_file in self._table_dropin_files:
            filename = Path(project.dropins_key, table_dropin_file)
            if self._check_dropin_file(GitLab_Table_Dropins_Parser, filename):
                has_table_dropins = True

        if has_table_dropins:
            self._check_update_file(project)
            has_dropins = True

        return has_dropins

    def _check_update_file(self, project: Project) -> None:
        update_path = Path(project.dropins_key, 'gitlab_update.json')
        if update_path.exists():
            with update_path.open('r', encoding='utf-8') as update_file:
                update_times: Dict[str, str] = json.load(update_file)
                if self.repo_name in update_times:
                    update_time = update_times[self.repo_name]
                    self._update_trackers["gitlab_update"] = update_time

    def _check_dropin_file(self, parser_class: Type[GitLab_Dropins_Parser],
                           filename: Path) -> bool:
        parser = parser_class(self, filename)
        return parser.parse()

    @classmethod
    def is_up_to_date(cls, source: Source, latest_version: Version,
                      update_tracker: Optional[str] = None,
                      branch: Optional[str] = None) -> bool:
        if branch is None:
            branch = 'master'

        try:
            project = cls._get_repo_project(source)
        except RuntimeError:
            return False

        # Check if the API indicates that there are updates
        if update_tracker is not None:
            tracker_date = get_local_datetime(update_tracker)
            activity_date = parse_utc_date(project.last_activity_at)
            if tracker_date < get_local_datetime(activity_date):
                return False

        # Use the API to fetch the latest commit of the branch
        try:
            current_version = str(project.commits.get(branch).id)
        except GitlabGetError:
            return False

        return current_version == latest_version

    @classmethod
    def _get_repo_project(cls, source: Source) -> gitlab.v4.objects.Project:
        if not isinstance(source, GitLab):
            raise RuntimeError('Source must be a GitLab source')

        try:
            repo_project = source.gitlab_api.projects.get(source.gitlab_path)
        except (AttributeError, GitlabAuthenticationError, GitlabGetError) as error:
            raise RuntimeError('Cannot access the GitLab API (insufficient credentials)') from error

        return repo_project

    @classmethod
    def get_compare_url(cls, source: Source, first_version: Version,
                        second_version: Optional[Version] = None) -> Optional[str]:
        if second_version is None:
            try:
                repo_project = cls._get_repo_project(source)
            except RuntimeError:
                # Cannot connect to API to retrieve web URL
                return None

            second_version = str(repo_project.default_branch)

        return f'{source.web_url}/compare/{first_version}...{second_version}'

    @classmethod
    def get_tree_url(cls, source: Source, version: Optional[Version] = None,
                     path: Optional[str] = None, line: Optional[int] = None) -> Optional[str]:
        if version is None:
            try:
                repo_project = cls._get_repo_project(source)
            except RuntimeError:
                # Cannot connect to API to retrieve web URL
                return None

            version = str(repo_project.default_branch)

        if path is None:
            path = ''
        line_anchor = f'#L{line}' if line is not None else ''
        return f'{source.web_url}/tree/{version}/{path}{line_anchor}'

    @property
    def source(self) -> GitLab:
        return cast(GitLab, self._source)

    @property
    def api(self) -> gitlab.Gitlab:
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        return self.source.gitlab_api

    @property
    def repo_project(self) -> gitlab.v4.objects.Project:
        """
        Retrieve the project object of this repository from the GitLab API.

        Raises a `RuntimeError` if the GitLab API cannot be accessed due to
        insufficient credentials.
        """

        if self._repo_project is None:
            try:
                self._repo_project = self._get_repo_project(self._source)
            except RuntimeError as error:
                raise RepositorySourceException('Cannot obtain project from API') from error

        return self._repo_project

    def get_data(self, from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None, force: bool = False,
                 **kwargs: Any) -> List[Dict[str, str]]:
        # Check if we can retrieve the data from legacy dropin files.
        has_dropins = self._check_dropin_files(self.project)

        versions = super().get_data(from_revision, to_revision,
                                    comments=has_dropins, force=force,
                                    **kwargs)

        self.fill_repo_table(self.repo_project)
        if not has_dropins:
            for event in self.repo_project.events.list(as_list=False):
                self.add_event(event)

            for request in self.repo_project.mergerequests.list(as_list=False):
                newer = self.add_merge_request(request)
                if newer:
                    for note in request.notes.list(as_list=False):
                        self.add_note(note, request.id)

        self.set_latest_date()

        return versions

    def fill_repo_table(self, repo_project: gitlab.v4.objects.Project) -> None:
        """
        Add the repository data from a GitLab API Project object `repo_project`
        to the table for GitLab repositories.
        """

        if repo_project.description is not None:
            description = parse_unicode(repo_project.description)
        else:
            description = str(0)

        if repo_project.avatar_url is not None:
            has_avatar = str(1)
        else:
            has_avatar = str(0)

        if repo_project.archived:
            archived = str(1)
        else:
            archived = str(0)

        self._tables["gitlab_repo"].append({
            'repo_name': str(self._repo_name),
            'gitlab_id': str(repo_project.id),
            'description': description,
            'create_time': parse_utc_date(repo_project.created_at),
            'archived': archived,
            'has_avatar': has_avatar,
            'star_count': str(repo_project.star_count)
        })

    def add_merge_request(self,
                          request: gitlab.v4.objects.ProjectMergeRequest) \
            -> bool:
        """
        Add a merge request described by its GitLab API response object to
        the merge requests table.

        Returns whether the merge request is newer than the most recent update.
        """

        updated_date = parse_utc_date(request.updated_at)
        if not self._is_newer(get_local_datetime(updated_date)):
            return False

        if request.assignee is not None:
            assignee = parse_unicode(request.assignee['name'])
            assignee_username = parse_unicode(request.assignee['username'])
        else:
            assignee = str(0)
            assignee_username = str(0)

        self._tables["merge_request"].append({
            'repo_name': str(self._repo_name),
            'id': str(request.id),
            'title': parse_unicode(request.title),
            'description': parse_unicode(request.description),
            'status': str(request.state),
            'source_branch': str(request.source_branch),
            'target_branch': str(request.target_branch),
            'author': parse_unicode(request.author['name']),
            'author_username': parse_unicode(request.author['username']),
            'assignee': assignee,
            'assignee_username': assignee_username,
            'upvotes': str(request.upvotes),
            'downvotes': str(request.downvotes),
            'created_at': parse_utc_date(request.created_at),
            'updated_at': updated_date
        })

        return True

    def add_note(self, note: gitlab.v4.objects.ProjectMergeRequestNote,
                 merge_request_id: int) -> None:
        """
        Add a note described by its GitLab API response object to the
        merge request notes table.
        """

        self._tables["merge_request_note"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': str(merge_request_id),
            'thread_id': str(0),
            'note_id': str(note.id),
            'parent_id': str(0),
            'author': parse_unicode(note.author['name']),
            'author_username': parse_unicode(note.author['username']),
            'comment': parse_unicode(note.body),
            'created_at': parse_utc_date(note.created_at)
        })

    def add_commit_comment(self, note: gitlab.v4.objects.ProjectCommitComment,
                           commit_id: Version) -> None:
        """
        Add a commit comment note dictionary to the commit comments table.
        """

        self._tables["commit_comment"].append({
            'repo_name': str(self._repo_name),
            'commit_id': str(commit_id),
            'merge_request_id': str(0),
            'thread_id': str(0),
            'note_id': str(0),
            'parent_id': str(0),
            'author': parse_unicode(note.author['name']),
            'author_username': parse_unicode(note.author['username']),
            'comment': parse_unicode(note.note),
            'file': note.path if note.path is not None else str(0),
            'line': str(note.line) if note.line is not None else str(0),
            'line_type': note.line_type if note.line_type is not None else str(0),
            'created_date': parse_utc_date(note.created_at)
        })

    @staticmethod
    def _parse_legacy_push_event(event: gitlab.v4.objects.Event,
                                 event_data: Dict[str, str]) -> List[str]:
        if event.data is None:
            return []

        event_data.update({
            'kind': str(event.data['object_kind']) if 'object_kind' in event.data else 'push',
            'ref': str(event.data['ref'])
        })

        if 'user_email' in event.data:
            event_data['email'] = parse_unicode(str(event.data['user_email']))
        if 'user_name' in event.data:
            event_data['user'] = parse_unicode(str(event.data['user_name']))
        if event_data['kind'] == 'tag_push':
            key = 'before' if event.action_name == 'deleted' else 'after'
            return [str(event.data[key])]
        if 'after' in event.data and event.data['after'][:8] == '00000000':
            event_data['action'] = 'deleted'
            return [str(event.data['before'])]

        commits = event.data['commits']
        if isinstance(commits, list):
            return [commit['id'] for commit in commits]

        return []

    def _parse_push_event(self, event: gitlab.v4.objects.Event,
                          event_data: Dict[str, str]) -> List[str]:
        event_data.update({
            'kind': str(event.push_data['ref_type']),
            'ref': str(event.push_data['ref']),
            'user': parse_unicode(event.author['name'])
        })

        ranges = {
            'commit_from': 'commit_to',
            'commit_to': 'commit_from'
        }

        for range_one, range_two in ranges.items():
            if event.push_data[range_one] is None:
                if event.push_data[range_two] is not None:
                    return [event.push_data[range_two]]

                return []

        if event_data['kind'] == 'tag':
            key = 'commit_from' if event.action_name == 'removed' else 'commit_to'
            return [event.push_data[key]]

        if event.push_data['commit_count'] == 1:
            return [event.push_data['commit_to']]

        refspec = f"{event.push_data['commit_from']}..{event.push_data['commit_to']}"
        try:
            query = self.repo.iter_commits(refspec)
            return [commit.hexsha for commit in query]
        except GitCommandError as error:
            logging.warning('Cannot find commit range %s: %s', refspec, error)
            return []

    def add_event(self, event: gitlab.v4.objects.Event) -> None:
        """
        Add an event from the GitLab API. Only relevant events are actually
        added to the events table.
        """

        if event.action_name in ('pushed to', 'pushed new', 'deleted'):
            created_date = parse_utc_date(event.created_at)
            if not self._is_newer(get_local_datetime(created_date)):
                return

            username = parse_unicode(event.author_username)
            event_data = {
                'repo_name': str(self._repo_name),
                'action': str(event.action_name),
                'user': username,
                'username': username,
                'email': str(0),
                'date': created_date
            }
            if 'data' in event.attributes and event.data is not None:
                # Legacy event push data
                commits = self._parse_legacy_push_event(event, event_data)
            else:
                # GitLab 9.5+ event push data (in v4 API since 9.6)
                commits = self._parse_push_event(event, event_data)

            for commit_id in commits:
                commit_event = event_data.copy()
                commit_event['version_id'] = str(commit_id)
                self._tables["vcs_event"].append(commit_event)

    def _parse_version(self, commit: Commit, stats: bool = True, **kwargs: Any) -> Dict[str, str]:
        data = super()._parse_version(commit, stats=stats, **kwargs)

        if self._has_commit_comments and kwargs.get('comments'):
            project_commit = self.repo_project.commits.get(commit.hexsha,
                                                           lazy=True)
            for comment in project_commit.comments.list(as_list=False):
                self.add_commit_comment(comment, commit.hexsha)

        return data
