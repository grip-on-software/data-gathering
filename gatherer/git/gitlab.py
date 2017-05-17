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
import gitlab3
from gitlab3.exceptions import GitLabException
from .repo import Git_Repository
from ..table import Table, Key_Table, Link_Table
from ..utils import convert_local_datetime, format_date, parse_date, parse_unicode

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
                     self._repo.repo_name, self._filename)
        if not os.path.exists(self._filename):
            logging.info('Dropin file %s does not exist', self._filename)
            return False

        with open(self._filename, 'r') as dropin_file:
            data = json.load(dropin_file)

        # Attempt to use the original path name
        path_name = self._repo.source.get_path_name(self._repo.source.plain_url)
        if path_name is None:
            logging.warning('Could not infer path name for repository: %s',
                            self._repo.repo_name)
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
        self._parse_legacy_data(self._repo.api, repo_data)

        logging.info('Read data from dropin file for repository %s',
                     self._repo.repo_name)

        return True

    def _parse_legacy_data(self, api, repo_data):
        raise NotImplementedError("Must be implemented by subclasses")

class GitLab_Main_Dropins_Parser(GitLab_Dropins_Parser):
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

class GitLab_Events_Dropins_Parser(GitLab_Dropins_Parser):
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

class GitLab_Repository(Git_Repository):
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

        author_fields = ('author', 'author_username')
        assignee_fields = ('assignee', 'assignee_username')
        self._tables.update({
            "gitlab_repo": Key_Table('gitlab_repo', 'gitlab_id'),
            "merge_request": Key_Table('merge_request', 'id',
                                       encrypted_fields=author_fields + assignee_fields),
            "merge_request_note": Link_Table('merge_request_note',
                                             ('merge_request_id', 'note_id'),
                                             encrypted_fields=author_fields),
            "commit_comment": Table('commit_comment',
                                    encrypted_fields=author_fields),
            "vcs_event": Table('vcs_event', encrypted_fields=('user', 'email'))
        })

    def _check_dropin_files(self, project=None):
        if project is None:
            return False

        filename = os.path.join(project.dropins_key, 'data_gitlabevents.json')
        self._check_dropin_file(GitLab_Events_Dropins_Parser, filename)

        filename = os.path.join(project.dropins_key, 'data_gitlab.json')
        if self._check_dropin_file(GitLab_Main_Dropins_Parser, filename):
            return True

        namespace = self._source.gitlab_namespace
        filename = os.path.join(project.dropins_key,
                                'data_gitlab_{}.json'.format(namespace))
        if self._check_dropin_file(GitLab_Main_Dropins_Parser, filename):
            return True

        return False

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

    @staticmethod
    def _create_api(source):
        try:
            logging.info('Setting up API for %s', source.host)
            return gitlab3.GitLab(source.host, source.gitlab_token)
        except (AttributeError, GitLabException):
            raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

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

    def get_data(self, **kwargs):
        # Check if we can retrieve the data from legacy dropin files.
        if self._check_dropin_files(self.project):
            comments = False
        else:
            comments = True

        versions = super(GitLab_Repository, self).get_data(comments=comments,
                                                           **kwargs)

        self.fill_repo_table(self.repo_project)
        for event in self.repo_project.events():
            self.add_event(event)

        for merge_request in self.repo_project.merge_requests():
            self.add_merge_request(merge_request)
            for note in merge_request.notes():
                self.add_note(note, merge_request.id)

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

    def add_note(self, note, merge_request_id):
        """
        Add a note described by its GitLab API response object to the
        merge request notes table.
        """

        self._tables["merge_request_note"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': str(merge_request_id),
            'note_id': str(note.id),
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

    def _parse_version(self, commit, comments=True, **kwargs):
        data = super(GitLab_Repository, self)._parse_version(commit, **kwargs)

        if self._has_commit_comments and comments:
            commit_comments = self.repo_project.get_comments(commit.hexsha)
            for comment in commit_comments:
                self.add_commit_comment(comment, commit.hexsha)

        return data
