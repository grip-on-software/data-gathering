"""
Package for classes related to extracting data from multiple Git repositories.
"""

import json
import logging
import os
from datetime import datetime
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
from .progress import Git_Progress
from ..utils import parse_unicode, Iterator_Limiter
from ..version_control import Version_Control_Repository

__all__ = ["Git_Repository"]

class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    DEFAULT_UPDATE_RATIO = 10

    def __init__(self, repo_name, repo_directory, credentials_path=None,
                 unsafe_hosts=True, **kwargs):
        super(Git_Repository, self).__init__(repo_name, repo_directory, **kwargs)
        self._repo = None
        self._credentials_path = credentials_path
        self._unsafe_hosts = unsafe_hosts

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
    def from_url(cls, repo_name, repo_directory, url, progress=True, **kwargs):
        """
        Initialize a Git repository from its clone URL if it does not yet exist.

        If `progress` is `True`, then add progress lines from Git commands to
        the logging output. If `progress` is a nonzero number, then sample from
        this number of lines. If it is not `False`, then use it as a progress
        callback function.

        The `credentials_path` specifies a path to an SSH private key identity
        file, which is then used for all Git-over-SSH communications. If this
        is `None`, then passworded or anonymous access must be used.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.
        """

        if progress is True:
            progress = Git_Progress(update_ratio=cls.DEFAULT_UPDATE_RATIO)
        elif not progress:
            progress = None
        elif isinstance(progress, int):
            progress = Git_Progress(update_ratio=progress)

        repository = cls(repo_name, repo_directory, **kwargs)
        if os.path.exists(repo_directory):
            if not repository.is_empty():
                # Update the repository from the origin URL.
                repository.repo.remotes.origin.pull('master', progress=progress)
        else:
            repository.repo = Repo.clone_from(url, repo_directory,
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
                ssh_command = "{} -oStrictHostKeyChecking=no".format(ssh_command)

            environment['GIT_SSH_COMMAND'] = ssh_command

        return environment

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

        data = []
        commits = self._query(refspec, paths=paths, descending=descending)
        had_commits = True
        count = 0
        while self._iterator_limiter.check(had_commits):
            had_commits = False

            for commit in commits:
                had_commits = True
                count += 1
                data.append(self.parse_commit(commit))

                if count % self._log_size == 0:
                    logging.info('Analysed commits up to %d', count)

            logging.info('Analysed batch of commits, now at %d', count)

            self._iterator_limiter.update()

            if self._iterator_limiter.check(had_commits):
                commits = self._query(refspec, paths=paths, descending=descending)

        return data


    def parse_commit(self, commit):
        """
        Convert one commit instance to a dictionary of properties.
        """

        commit_datetime = datetime.fromtimestamp(commit.committed_date)

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
            'commit_date': datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')
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
