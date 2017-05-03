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
from ..utils import convert_local_datetime, format_date, parse_unicode

class GitLab_Repository(Git_Repository):
    """
    Git repository hosted by a GitLab instance.
    """

    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(GitLab_Repository, self).__init__(source, repo_directory,
                                                project=project, **kwargs)
        self._api = None
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
                                    encrypted_fields=author_fields)
        })

    def _check_dropin_files(self, project=None):
        if project is None:
            return False

        filename = os.path.join(project.dropins_key, 'data_gitlab.json')
        if self._check_dropin_file(filename):
            return True

        namespace = self._source.gitlab_namespace
        filename = os.path.join(project.dropins_key,
                                'data_gitlab_{}.json'.format(namespace))
        if self._check_dropin_file(filename):
            return True

        return False

    def _check_dropin_file(self, filename):
        logging.info('%s: Checking dropin file %s', self._repo_name, filename)
        if not os.path.exists(filename):
            logging.info('Dropin file %s does not exist', filename)
            return False

        with open(filename, 'r') as dropin_file:
            data = json.load(dropin_file)

        # Attempt to use the original path name
        path_name = self._source.get_path_name(self._source.plain_url)
        if path_name is None:
            logging.warning('Could not infer repository: %s', self._repo_name)
            return False

        if path_name not in data:
            logging.warning('Repository %s not in GitLab data', path_name)
            return False

        # Fill GitLab API objects with the JSON data.
        repo_data = data[path_name]
        self._parse_legacy_data(repo_data)

        logging.info('Read data from dropin file for repo %s', self._repo_name)

        return True

    def _parse_legacy_data(self, repo_data):
        # Load the Project sub-API in the gitlab3 module. This class is only
        # created once the main API is instantiated.
        api = self.api
        if not hasattr(api, 'Project'):
            raise RuntimeError('Could not load project GitLab API definition')

        project_class = getattr(api, 'Project')

        repo_project = project_class(api, json_data=repo_data['info'])

        self._fill_repo_table(repo_project)

        for merge_request in repo_data['merge_requests']:
            request = repo_project.MergeRequest(repo_project,
                                                json_data=merge_request['info'])
            self._add_merge_request(request)
            for note in merge_request['notes']:
                self._add_note(request.Note(request, json_data=note),
                               request.id)

        for commit_id, comments in repo_data['commit_comments'].items():
            commit = repo_project.Commit(repo_project,
                                         json_data=comments['commit_info'])
            commit_datetime = convert_local_datetime(commit.committed_date)
            updated_commit_id = self.find_commit(commit_datetime)
            if updated_commit_id is None:
                logging.warning('Could not find updated commit ID for %s at %s',
                                commit_id, commit.committed_date.isoformat())
                updated_commit_id = commit_id

            for comment in comments['notes']:
                self._add_commit_comment(comment, updated_commit_id)

    @classmethod
    def is_up_to_date(cls, source, latest_version):
        try:
            api = cls._create_api(source)
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

        if self._api is None:
            self._api = self._create_api(self._source)

        return self._api

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

        self._fill_repo_table(self.repo_project)

        for merge_request in self.repo_project.merge_requests():
            self._add_merge_request(merge_request)
            for note in merge_request.notes():
                self._add_note(note, merge_request.id)

        return versions

    def _fill_repo_table(self, repo_project):
        # Skip filling the repo table if it was already filled from a dropin.
        if self._tables["gitlab_repo"]:
            return

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

        self._tables["gitlab_repo"] = [
            {
                'repo_name': str(self._repo_name),
                'gitlab_id': str(repo_project.id),
                'description': description,
                'create_time': format_date(repo_project.created_at),
                'archived': archived,
                'has_avatar': has_avatar,
                'star_count': star_count
            }
        ]

    def _add_merge_request(self, merge_request):
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

    def _add_note(self, note, merge_request_id):
        self._tables["merge_request_note"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': str(merge_request_id),
            'note_id': str(note.id),
            'author': parse_unicode(note.author['name']),
            'author_username': parse_unicode(note.author['username']),
            'comment': parse_unicode(note.body),
            'created_at': format_date(note.created_at)
        })

    def _add_commit_comment(self, note, commit_id):
        self._tables["commit_comment"].append({
            'repo_name': str(self._repo_name),
            'commit_id': str(commit_id),
            'author': parse_unicode(note['author']['name']),
            'author_username': parse_unicode(note['author']['username']),
            'comment': parse_unicode(note['note']),
            'file': note['path'] if note['path'] is not None else str(0),
            'line': str(note['line']) if note['line'] is not None else str(0),
            'line_type': note['line_type'] if note['line_type'] is not None else str(0)
        })

    def _parse_version(self, commit, comments=True, **kwargs):
        data = super(GitLab_Repository, self)._parse_version(commit, **kwargs)

        if self._has_commit_comments and comments:
            commit_comments = self.repo_project.get_comments(commit.hexsha)
            for comment in commit_comments:
                self._add_commit_comment(comment, commit.hexsha)

        return data
