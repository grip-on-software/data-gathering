"""
Package for classes related to extracting data from multiple Git repositories.
"""

import json
import logging
import os
from datetime import datetime
import urllib
import dateutil.tz
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
from gitlab3 import GitLab
from gitlab3.exceptions import GitLabException
from .progress import Git_Progress
from ..utils import format_date, parse_unicode, Iterator_Limiter
from ..version_control import Version_Control_Repository

__all__ = ["Git_Repository", "GitLab_Repository"]

class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    DEFAULT_UPDATE_RATIO = 10

    def __init__(self, source, repo_directory, **kwargs):
        super(Git_Repository, self).__init__(source, repo_directory, **kwargs)
        self._repo = None
        self._credentials_path = source.credentials_path
        self._unsafe_hosts = bool(source.get_option('unsafe'))

        self._iterator_limiter = None
        self._batch_size = 10000
        self._log_size = 1000
        self._reset_limiter()

    def _reset_limiter(self):
        self._iterator_limiter = Iterator_Limiter(size=self._batch_size)

    @staticmethod
    def _get_refspec(from_revision=None, to_revision=None):
        if from_revision is not None and to_revision is not None:
            return '{}...{}'.format(from_revision, to_revision)
        elif from_revision is not None:
            return '{}...master'.format(from_revision)
        elif to_revision is not None:
            return to_revision
        else:
            return None

    @classmethod
    def from_source(cls, source, repo_directory, progress=True, **kwargs):
        """
        Initialize a Git repository from its `Source` domain object.

        If `progress` is `True`, then add progress lines from Git commands to
        the logging output. If `progress` is a nonzero number, then sample from
        this number of lines. If it is not `False`, then use it as a progress
        callback function.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.
        """

        if progress is True:
            progress = Git_Progress(update_ratio=cls.DEFAULT_UPDATE_RATIO)
        elif not progress:
            progress = None
        elif isinstance(progress, int):
            progress = Git_Progress(update_ratio=progress)

        repository = cls(source, repo_directory, **kwargs)
        if os.path.exists(repo_directory):
            if not repository.is_empty():
                # Update the repository from the origin URL.
                repository.repo.remotes.origin.pull('master', progress=progress)
        else:
            repository.repo = Repo.clone_from(source.url, repo_directory,
                                              progress=progress,
                                              env=repository.environment)

        return repository

    @property
    def repo(self):
        if self._repo is None:
            # Use property setter for updating the environment credentials path
            self.repo = Repo(self._repo_directory)

        return self._repo

    @repo.setter
    def repo(self, repo):
        if not isinstance(repo, Repo):
            raise TypeError('Repository must be a gitpython Repo instance')

        repo.git.update_environment(**self.environment)
        self._repo = repo

    @property
    def environment(self):
        """
        Retrieve the environment variables for the Git subcommands.
        """

        environment = {}

        if self._credentials_path is not None:
            logging.debug('Using credentials path %s', self._credentials_path)
            ssh_command = "ssh -i '{}'".format(self._credentials_path)
            if self._unsafe_hosts:
                ssh_command += '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

            environment['GIT_SSH_COMMAND'] = ssh_command

        return environment

    @property
    def version_info(self):
        return self.repo.git.version_info

    def exists(self):
        """
        Check whether the repository exists, i.e., the path points to a valid
        Git repository.
        """

        try:
            return bool(self.repo)
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False

    def is_empty(self):
        """
        Check whether the repository is empty, i.e. no commits have been made
        at all.
        """

        return not self.repo.branches

    def _query(self, refspec, paths='', descending=True):
        return self.repo.iter_commits(refspec, paths=paths,
                                      max_count=self._iterator_limiter.size,
                                      skip=self._iterator_limiter.skip,
                                      reverse=not descending)

    def get_versions(self, filename='', from_revision=None, to_revision=None, descending=False):
        refspec = self._get_refspec(from_revision, to_revision)
        return self._parse(refspec, paths=filename, descending=descending)

    def _parse(self, refspec, paths='', descending=True):
        self._reset_limiter()

        version_data = []
        commits = self._query(refspec, paths=paths, descending=descending)
        had_commits = True
        count = 0
        while self._iterator_limiter.check(had_commits):
            had_commits = False

            for commit in commits:
                had_commits = True
                count += 1
                version_data.append(self.parse_commit(commit))

                if count % self._log_size == 0:
                    logging.info('Analysed commits up to %d', count)

            logging.info('Analysed batch of commits, now at %d', count)

            self._iterator_limiter.update()

            if self._iterator_limiter.check(had_commits):
                commits = self._query(refspec, paths=paths, descending=descending)

        return version_data


    def parse_commit(self, commit):
        """
        Convert one commit instance to a dictionary of properties.
        """

        commit_datetime = commit.committed_datetime.astimezone(dateutil.tz.tzlocal())

        commit_type = str(commit.type)
        if len(commit.parents) > 1:
            commit_type = 'merge'

        git_commit = {
            # Primary data
            'repo_name': str(self._repo_name),
            'version_id': str(commit.hexsha),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(commit.message),
            'type': commit_type,
            'developer': commit.author.name,
            'developer_email': str(commit.author.email),
            'commit_date': format_date(commit_datetime)
        }

        if self.retrieve_stats:
            git_commit.update(self._get_diff_stats(commit))


        return git_commit

    @staticmethod
    def _get_diff_stats(commit):
        cstotal = commit.stats.total

        return {
            # Statistics
            'insertions': str(cstotal['insertions']),
            'deletions': str(cstotal['deletions']),
            'number_of_files': str(cstotal['files']),
            'number_of_lines': str(cstotal['lines']),
            'size': str(commit.size)
        }

    def get_latest_version(self):
        return self.repo.rev_parse('master').hexsha

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
            "gitlab": [],
            "merge_requests": [],
            "merge_request_notes": [],
            "commit_comments": []
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

        self._tables["gitlab"] = [
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

        self._tables["merge_requests"].append({
            'repo_name': str(self._repo_name),
            'id': str(merge_request.id),
            'title': merge_request.title,
            'description': merge_request.description,
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
            'comment': note.body,
            'created_at': format_date(note.created_at)
        })

    def _add_commit_comment(self, note, commit_id):
        self._tables["commit_comments"].append({
            'repo_name': str(self._repo_name),
            'commit_id': str(commit_id),
            'author': note.author.name,
            'comment': note.note,
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
