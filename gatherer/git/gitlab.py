"""
Module that handles access to a GitLab-based repository, augmenting the usual
repository version information with merge requests and commit comments.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import str
import json
import logging
import os
from .repo import Git_Repository
from ..table import Table, Key_Table
from ..utils import convert_local_datetime, format_date, parse_date, \
    parse_unicode
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

class GitLab_Combined_Dropins_Parser(GitLab_Dropins_Parser):
    """
    Parser for dropins that contain a JSON object of repository keys and
    legacy data values from the GitLab API.
    """

    def _parse(self, data):
        # Attempt to use the original path name
        path_name = self.repo.source.get_path_name(self.repo.source.plain_url)
        if path_name is None:
            logging.warning('Could not infer path name for repository: %s',
                            self.repo.repo_name)
            return False

        if path_name not in data:
            logging.warning('Repository %s not in GitLab data', path_name)
            return False

        # Retrieve the GitLab API dictionaries from the JSON data.
        repo_data = data[path_name]
        # Load the GitLab API in the gitlab3 module by creating the API object
        # from the repository object. This ensures that the API also loads the
        # sub-API's, such as Project.
        # Pass along the API and the repository data to the parser.
        self._parse_legacy_data(self.repo.api, repo_data)

        logging.info('Read data from dropin file for repository %s',
                     self.repo.repo_name)

        return True

    def _parse_legacy_data(self, api, repo_data):
        raise NotImplementedError("Must be implemented by subclasses")

class GitLab_Main_Dropins_Parser(GitLab_Combined_Dropins_Parser):
    """
    Parser for dropin files that contain repository information as well as
    commit comments, merge requests and merge request notes from GitLab API.
    """

    def _parse_legacy_data(self, api, repo_data):
        if not hasattr(api, 'Project'):
            raise RuntimeError('Could not load project GitLab API definition')

        project_class = getattr(api, 'Project')

        repo_project = project_class(api, json_data=repo_data['info'])

        self.repo.fill_repo_table(repo_project)

        for merge_request in repo_data['merge_requests']:
            request = repo_project.MergeRequest(repo_project,
                                                json_data=merge_request['info'])
            self.repo.add_merge_request(request)
            for note in merge_request['notes']:
                self.repo.add_note(request.Note(request, json_data=note),
                                   request.id)

        for commit_id, comments in repo_data['commit_comments'].items():
            commit = repo_project.Commit(repo_project,
                                         json_data=comments['commit_info'])
            commit_datetime = convert_local_datetime(commit.committed_date)
            updated_commit_id = self.repo.find_commit(commit_datetime)
            if updated_commit_id is None:
                logging.warning('Could not find updated commit ID for %s at %s',
                                commit_id, commit.committed_date.isoformat())
                updated_commit_id = commit_id

            for comment in comments['notes']:
                self.repo.add_commit_comment(comment, updated_commit_id)

class GitLab_Events_Dropins_Parser(GitLab_Combined_Dropins_Parser):
    """
    Parser for dropin files that contain events for repositories as extracted
    from the GitLab API.
    """

    def _parse_legacy_data(self, api, repo_data):
        if not hasattr(api, 'Project'):
            raise RuntimeError('Could not load project GitLab API definition')

        for event_data in repo_data['events']:
            event = api.Project.Event(api, json_data=event_data)
            self.repo.add_event(event)

class GitLab_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by a GitLab instance.
    """

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
            "vcs_event": Table('vcs_event', encrypted_fields=('user', 'email'))
        })
        return review_tables

    @property
    def update_tracker_name(self):
        return "gitlab_update"

    def _check_dropin_files(self, project=None):
        if project is None:
            return False

        has_dropins = False

        filename = os.path.join(project.dropins_key, 'data_gitlabevents.json')
        self._check_dropin_file(GitLab_Events_Dropins_Parser, filename)

        filename = os.path.join(project.dropins_key, 'data_gitlab.json')
        if self._check_dropin_file(GitLab_Main_Dropins_Parser, filename):
            has_dropins = True

        namespace = self._source.gitlab_namespace
        filename = os.path.join(project.dropins_key,
                                'data_gitlab_{}.json'.format(namespace))
        if not has_dropins and \
            self._check_dropin_file(GitLab_Main_Dropins_Parser, filename):
            has_dropins = True

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
    def is_up_to_date(cls, source, latest_version):
        try:
            api = source.gitlab_api
        except RuntimeError:
            return False

        # pylint: disable=no-member
        project = api.project(source.gitlab_path)
        if project.commit('HEAD').id == latest_version:
            return True

        return False

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
        """

        if self._repo_project is None:
            try:
                self._repo_project = self.api.project(self._source.gitlab_path)
            except AttributeError:
                raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

        return self._repo_project

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        # Check if we can retrieve the data from legacy dropin files.
        has_dropins = self._check_dropin_files(self.project)

        versions = super(GitLab_Repository, self).get_data(from_revision,
                                                           to_revision,
                                                           comments=has_dropins,
                                                           **kwargs)

        self.fill_repo_table(self.repo_project)
        if not has_dropins:
            for event in self.repo_project.events():
                self.add_event(event)

            for merge_request in self.repo_project.merge_requests():
                newer = self.add_merge_request(merge_request)
                if newer:
                    for note in merge_request.notes():
                        self.add_note(note, merge_request.id)

        if self._latest_date is not None:
            latest_date = format_date(convert_local_datetime(self._latest_date))
            self._update_trackers['gitlab_update'] = latest_date

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

        if hasattr(repo_project, 'star_count'):
            star_count = str(repo_project.star_count)
        else:
            star_count = str(0)

        self._tables["gitlab_repo"].append({
            'repo_name': str(self._repo_name),
            'gitlab_id': str(repo_project.id),
            'description': description,
            'create_time': format_date(repo_project.created_at),
            'archived': archived,
            'has_avatar': has_avatar,
            'star_count': star_count
        })

    def add_merge_request(self, merge_request):
        """
        Add a merge request described by its GitLab API response object to
        the merge requests table.
        """

        if not self._is_newer(merge_request.updated_at):
            return False

        if merge_request.assignee is not None:
            assignee = parse_unicode(merge_request.assignee['name'])
            assignee_username = parse_unicode(merge_request.assignee['username'])
        else:
            assignee = str(0)
            assignee_username = str(0)

        self._tables["merge_request"].append({
            'repo_name': str(self._repo_name),
            'id': str(merge_request.id),
            'title': parse_unicode(merge_request.title),
            'description': parse_unicode(merge_request.description),
            'status': merge_request.state,
            'source_branch': merge_request.source_branch,
            'target_branch': merge_request.target_branch,
            'author': parse_unicode(merge_request.author['name']),
            'author_username': parse_unicode(merge_request.author['username']),
            'assignee': assignee,
            'assignee_username': assignee_username,
            'upvotes': str(merge_request.upvotes),
            'downvotes': str(merge_request.downvotes),
            'created_at': format_date(merge_request.created_at),
            'updated_at': format_date(merge_request.updated_at)
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
            'created_at': format_date(note.created_at)
        })

    def add_commit_comment(self, note, commit_id):
        """
        Add a commit comment note dictionary to the commit comments table.
        """

        if 'created_at' in note and note['created_at'] is not None:
            created_date = parse_date(note['created_at'])
        else:
            created_date = str(0)

        self._tables["commit_comment"].append({
            'repo_name': str(self._repo_name),
            'commit_id': str(commit_id),
            'merge_request_id': str(0),
            'thread_id': str(0),
            'note_id': str(0),
            'parent_id': str(0),
            'author': parse_unicode(note['author']['name']),
            'author_username': parse_unicode(note['author']['username']),
            'comment': parse_unicode(note['note']),
            'file': note['path'] if note['path'] is not None else str(0),
            'line': str(note['line']) if note['line'] is not None else str(0),
            'line_type': note['line_type'] if note['line_type'] is not None else str(0),
            'created_date': created_date
        })

    def add_event(self, event):
        """
        Add an event from the GitLab API. Only relevant events are actually
        added to the events table.
        """

        if event.action_name in ('pushed to', 'pushed new', 'deleted'):
            if not self._is_newer(event.created_at):
                return

            created_date = format_date(event.created_at)
            if event.data['object_kind'] == 'tag_push':
                if event.action_name == 'deleted':
                    commits = [event.data['before']]
                else:
                    commits = [event.data['after']]
            else:
                commits = [commit['id'] for commit in event.data['commits']]

            for commit_id in commits:
                self._tables["vcs_event"].append({
                    'repo_name': str(self._repo_name),
                    'version_id': str(commit_id),
                    'action': str(event.action_name),
                    'kind': str(event.data['object_kind']),
                    'ref': str(event.data['ref']),
                    'user': parse_unicode(event.author_username),
                    'email': str(event.data['user_email']),
                    'date': created_date
                })

    def _parse_version(self, commit, stats=True, **kwargs):
        data = super(GitLab_Repository, self)._parse_version(commit,
                                                             stats=stats,
                                                             **kwargs)

        if self._has_commit_comments and 'comments' in kwargs and kwargs['comments']:
            commit_comments = self.repo_project.get_comments(commit.hexsha)
            for comment in commit_comments:
                self.add_commit_comment(comment, commit.hexsha)

        return data
