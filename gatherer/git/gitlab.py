"""
Module that handles access to a GitLab-based repository, augmenting the usual
repository version information with merge requests and commit comments.
"""

import logging
import urllib
from gitlab3 import GitLab
from gitlab3.exceptions import GitLabException
from .repo import Git_Repository
from ..utils import format_date, parse_unicode

class GitLab_Repository(Git_Repository):
    """
    Git repository hosted by a GitLab instance.
    """

    def __init__(self, source, repo_directory, **kwargs):
        super(GitLab_Repository, self).__init__(source, repo_directory, **kwargs)
        self._api = None
        self._project = None
        has_commit_comments = self._source.get_option('has_commit_comments')
        if has_commit_comments is not None:
            self._has_commit_comments = has_commit_comments
        else:
            self._has_commit_comments = True

        self._tables.update({
            "gitlab_repo": [],
            "merge_request": [],
            "merge_request_note": [],
            "commit_comment": []
        })

    @property
    def api(self):
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        if self._api is None:
            try:
                logging.info('Setting up API for %s', self._source.host)
                self._api = GitLab(self._source.host, self._source.gitlab_token)
            except (AttributeError, GitLabException):
                raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

        return self._api

    @property
    def project(self):
        """
        Retrieve the project object of this repository from the GitLab API.
        """

        if self._project is None:
            try:
                path = urllib.quote_plus(self._source.gitlab_path)
                self._project = self.api.project(path)
            except AttributeError:
                raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

        return self._project

    def _parse(self, refspec, **kwargs):
        version_data = super(GitLab_Repository, self)._parse(refspec, **kwargs)

        if self.project.description is not None:
            description = self.project.description
        else:
            description = str(0)
        archived = str(1) if self.project.archived else str(0)
        has_avatar = str(1) if self.project.avatar_url is not None else str(0)

        self._tables["gitlab_repo"] = [
            {
                'repo_name': str(self._repo_name),
                'gitlab_id': str(self.project.id),
                'description': description,
                'create_time': format_date(self.project.created_at),
                'archived': archived,
                'has_avatar': has_avatar,
                'star_count': str(self.project.star_count)
            }
        ]

        for merge_request in self.project.merge_requests():
            self._add_merge_request(merge_request)

        return version_data

    def _add_merge_request(self, merge_request):
        if merge_request.assignee is not None:
            assignee = merge_request.assignee.name
        else:
            assignee = str(0)

        self._tables["merge_request"].append({
            'repo_name': str(self._repo_name),
            'id': str(merge_request.id),
            'title': parse_unicode(merge_request.title),
            'description': parse_unicode(merge_request.description),
            'source_branch': merge_request.source_branch,
            'target_branch': merge_request.target_branch,
            'author': merge_request.author.name,
            'assignee': assignee,
            'upvotes': str(merge_request.upvotes),
            'downvotes': str(merge_request.downvotes),
            'created_at': format_date(merge_request.created_at),
            'updated_at': format_date(merge_request.updated_at)
        })

        for note in merge_request.notes():
            self._add_note(note, merge_request.id)

    def _add_note(self, note, merge_request_id):
        self._tables["merge_request_notes"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': str(merge_request_id),
            'note_id': str(note.id),
            'author': note.author.name,
            'comment': parse_unicode(note.body),
            'created_at': format_date(note.created_at)
        })

    def _add_commit_comment(self, note, commit_id):
        self._tables["commit_comment"].append({
            'repo_name': str(self._repo_name),
            'commit_id': str(commit_id),
            'author': note.author.name,
            'comment': parse_unicode(note.note),
            'file': note.path,
            'line': str(note.line),
            'line_type': note.line_type
        })

    def parse_commit(self, commit):
        git_commit = super(GitLab_Repository, self).parse_commit(commit)

        if self._has_commit_comments:
            comments = self.project.get_comments(commit.hexsha)
            for comment in comments:
                self._add_commit_comment(comment, commit.hexsha)

        return git_commit
