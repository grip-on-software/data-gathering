"""
Module that handles access to a GitLab-based repository, augmenting the usual
repository version information with merge requests and commit comments.
"""

from __future__ import absolute_import
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import str
import json
import logging
import os
from git import GitCommandError
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError
from .repo import Git_Repository, RepositorySourceException
from ..table import Table, Key_Table
from ..utils import format_date, get_local_datetime, get_utc_datetime, \
    convert_local_datetime, parse_utc_date, parse_unicode
from ..version_control.review import Review_System

class GitLab_Dropins_Parser(object):
    """
    Parser for dropins containing an exported version of GitLab API responses.
    """

    def __init__(self, repo, filename):
        self._repo = repo
        self._filename = filename

    @property
    def repo(self):
        """
        Retrieve the repository that this dropin parser feeds.
        """

        return self._repo

    @property
    def filename(self):
        """
        Retrieve the path to the dropin file that is parsed.
        """

        return self._filename

    def parse(self):
        """
        Check whether the dropin file can be found and parse it if so.

        Returns a boolean indicating if any data for the repository could be
        retrieved.
        """

        logging.info('Repository %s: Checking dropin file %s',
                     self.repo.repo_name, self._filename)
        if not os.path.exists(self._filename):
            logging.info('Dropin file %s does not exist', self._filename)
            return False

        with open(self._filename, 'r') as dropin_file:
            data = json.load(dropin_file)

        return self._parse(data)

    def _parse(self, data):
        raise NotImplementedError('Must be implemented by subclasses')

class GitLab_Table_Dropins_Parser(GitLab_Dropins_Parser):
    """
    Parser for dropins that contain a list of JSON objects, which may be
    relevant to the current repository.
    """

    def __init__(self, repo, filename):
        super(GitLab_Table_Dropins_Parser, self).__init__(repo, filename)

        self._table = None
        basename = os.path.basename(self.filename)
        if basename.startswith('data_') and basename.endswith('.json'):
            table_name = filename[len('data_'):-len('.json')]
            tables = self.repo.tables
            if table_name in tables:
                self._table = tables[table_name]

    def _parse(self, data):
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

    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(GitLab_Repository, self).__init__(source, repo_directory,
                                                project=project, **kwargs)
        self._repo_project = None
        has_commit_comments = self._source.get_option('has_commit_comments')
        if has_commit_comments is not None:
            self._has_commit_comments = has_commit_comments
        else:
            self._has_commit_comments = True

        # List of dropin files that contain table data for GitLab only.
        self._table_dropin_files = tuple([
            'data_{}.json'.format(table) for table in self.review_tables
        ])

    @property
    def review_tables(self):
        review_tables = super(GitLab_Repository, self).review_tables
        review_tables.update({
            "gitlab_repo": Key_Table('gitlab_repo', 'gitlab_id'),
            "vcs_event": Table('vcs_event',
                               encrypt_fields=('user', 'username', 'email'))
        })
        return review_tables

    def _check_dropin_files(self, project=None):
        if project is None:
            return False

        has_dropins = False
        has_table_dropins = False
        for table_dropin_file in self._table_dropin_files:
            filename = os.path.join(project.dropins_key, table_dropin_file)
            if self._check_dropin_file(GitLab_Table_Dropins_Parser, filename):
                has_table_dropins = True

        if has_table_dropins:
            self._check_update_file(project)
            has_dropins = True

        return has_dropins

    def _check_update_file(self, project):
        update_path = os.path.join(project.dropins_key, 'gitlab_update.json')
        if os.path.exists(update_path):
            with open(update_path) as update_file:
                update_times = json.load(update_file)
                if self.repo_name in update_times:
                    update_time = update_times[self.repo_name]
                    self._update_trackers["gitlab_update"] = update_time

    def _check_dropin_file(self, parser_class, filename):
        parser = parser_class(self, filename)
        return parser.parse()

    @classmethod
    def is_up_to_date(cls, source, latest_version, update_tracker=None):
        try:
            project = cls._get_repo_project(source)
        except RuntimeError:
            return False

        # Check if the API indicates that there are updates
        if update_tracker is not None:
            tracker_date = get_local_datetime(update_tracker)
            activity_date = get_utc_datetime(project.last_activity_at,
                                             cls.ISO8601_FORMAT)
            if tracker_date < activity_date:
                return False

        # Use the API to fetch the latest commit
        if project.commits.get('HEAD').id == latest_version:
            return True

        return False

    @classmethod
    def _get_repo_project(cls, source):
        try:
            repo_project = source.gitlab_api.projects.get(source.gitlab_path)
        except (AttributeError, GitlabAuthenticationError, GitlabGetError):
            raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

        return repo_project

    @classmethod
    def get_compare_url(cls, source, first_version, second_version=None):
        if second_version is None:
            try:
                repo_project = cls._get_repo_project(source)
            except RuntimeError:
                # Cannot connect to API to retrieve web URL
                return None

            second_version = repo_project.default_branch

        return '{}/compare/{}...{}'.format(source.web_url, first_version,
                                           second_version)

    @classmethod
    def get_tree_url(cls, source, version=None, path=None, line=None):
        if version is None:
            try:
                repo_project = cls._get_repo_project(source)
            except RuntimeError:
                # Cannot connect to API to retrieve web URL
                return None

            version = repo_project.default_branch

        return '{}/tree/{}/{}{}'.format(source.web_url, version,
                                        path if path is not None else '',
                                        '#L{}'.format(line) if line is not None else '')

    @property
    def api(self):
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        return self._source.gitlab_api

    @property
    def repo_project(self):
        """
        Retrieve the project object of this repository from the GitLab API.

        Raises a `RuntimeError` if the GitLab API cannot be accessed due to
        insufficient credentials.
        """

        if self._repo_project is None:
            try:
                self._repo_project = self._get_repo_project(self._source)
            except RuntimeError:
                raise RepositorySourceException('Cannot obtain project from API')

        return self._repo_project

    def get_data(self, from_revision=None, to_revision=None, force=False, **kwargs):
        # Check if we can retrieve the data from legacy dropin files.
        has_dropins = self._check_dropin_files(self.project)

        versions = super(GitLab_Repository, self).get_data(from_revision,
                                                           to_revision,
                                                           comments=has_dropins,
                                                           force=force,
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

    def fill_repo_table(self, repo_project):
        """
        Add the repository data from a GitLab API Project object `repo_project`
        to the table for GitLab repositories.
        """

        if repo_project.description is not None:
            description = repo_project.description
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

    def add_merge_request(self, request):
        """
        Add a merge request described by its GitLab API response object to
        the merge requests table.
        """

        updated_date = get_utc_datetime(request.updated_at, self.ISO8601_FORMAT)
        if not self._is_newer(updated_date):
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
            'status': request.state,
            'source_branch': request.source_branch,
            'target_branch': request.target_branch,
            'author': parse_unicode(request.author['name']),
            'author_username': parse_unicode(request.author['username']),
            'assignee': assignee,
            'assignee_username': assignee_username,
            'upvotes': str(request.upvotes),
            'downvotes': str(request.downvotes),
            'created_at': parse_utc_date(request.created_at),
            'updated_at': format_date(convert_local_datetime(updated_date))
        })

        return True

    def add_note(self, note, merge_request_id):
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

    def add_commit_comment(self, note, commit_id):
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
    def _parse_legacy_push_event(event, event_data):
        event_data.update({
            'kind': str(event.data['object_kind']) if 'object_kind' in event.data else 'push',
            'ref': str(event.data['ref'])
        })

        if 'user_email' in event.data:
            event_data['email'] = parse_unicode(event.data['user_email'])
        if 'user_name' in event.data:
            event_data['user'] = parse_unicode(event.data['user_name'])
        if event_data['kind'] == 'tag_push':
            key = 'before' if event.action_name == 'deleted' else 'after'
            return [event.data[key]]
        if 'after' in event.data and event.data['after'][:8] == '00000000':
            event_data['action'] = 'deleted'
            return [event.data['before']]

        return [commit['id'] for commit in event.data['commits']]

    def _parse_push_event(self, event, event_data):
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

        refspec = '{}..{}'.format(event.push_data['commit_from'],
                                  event.push_data['commit_to'])
        try:
            query = self.repo.iter_commits(refspec)
            return [commit.hexsha for commit in query]
        except GitCommandError as error:
            logging.warning('Cannot find commit range %s: %s', refspec, error)
            return []

    def add_event(self, event):
        """
        Add an event from the GitLab API. Only relevant events are actually
        added to the events table.
        """

        if event.action_name in ('pushed to', 'pushed new', 'deleted'):
            created_date = get_utc_datetime(event.created_at,
                                            '%Y-%m-%dT%H:%M:%S.%fZ')
            if not self._is_newer(created_date):
                return

            username = parse_unicode(event.author_username)
            event_data = {
                'repo_name': str(self._repo_name),
                'action': str(event.action_name),
                'user': username,
                'username': username,
                'email': str(0),
                'date': format_date(convert_local_datetime(created_date))
            }
            if event.data is not None:
                # Legacy event push data
                commits = self._parse_legacy_push_event(event, event_data)
            else:
                # GitLab 9.5+ event push data (in v4 API since 9.6)
                commits = self._parse_push_event(event, event_data)

            for commit_id in commits:
                commit_event = event_data.copy()
                commit_event['version_id'] = str(commit_id)
                self._tables["vcs_event"].append(commit_event)

    def _parse_version(self, commit, stats=True, **kwargs):
        data = super(GitLab_Repository, self)._parse_version(commit,
                                                             stats=stats,
                                                             **kwargs)

        if self._has_commit_comments and 'comments' in kwargs and kwargs['comments']:
            project_commit = self.repo_project.commit(commit.hexsha, lazy=True)
            for comment in project_commit.comments.list(as_list=False):
                self.add_commit_comment(comment, commit.hexsha)

        return data
