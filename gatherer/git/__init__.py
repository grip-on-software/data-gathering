"""
Package for classes related to extracting data from multiple Git repositories.
"""

import json
import logging
import os
from datetime import datetime
from git import Repo, RemoteProgress
from ..utils import parse_unicode, Iterator_Limiter
from ..version_control import Version_Control_Repository

__all__ = ["Git_Repository"]

class Git_Progress(RemoteProgress):
    """
    Progress delegate which outputs Git progress to logging.
    """

    _op_codes = {
        RemoteProgress.COUNTING: 'Counting objects',
        RemoteProgress.COMPRESSING: 'Compressing objects',
        RemoteProgress.WRITING: 'Writing objects',
        RemoteProgress.RECEIVING: 'Receiving objects',
        RemoteProgress.RESOLVING: 'Resolving deltas',
        RemoteProgress.FINDING_SOURCES: 'Finding sources',
        RemoteProgress.CHECKING_OUT: 'Checking out files'
    }

    def update(self, op_code, cur_count, max_count=None, message=''):
        stage_op = op_code & RemoteProgress.STAGE_MASK
        action_op = op_code & RemoteProgress.OP_MASK
        if action_op in self._op_codes:
            if max_count is not None and max_count != '':
                ratio = cur_count / float(max_count)
                count = '{0:>3.0%} ({1:.0}/{2:.0})'.format(ratio, cur_count,
                                                           max_count)
            else:
                count = cur_count

            if stage_op == RemoteProgress.END:
                token = RemoteProgress.TOKEN_SEPARATOR + RemoteProgress.DONE_TOKEN
            else:
                token = ''

            line = '{0}: {1}{2}'.format(self._op_codes[action_op], count, token)
            logging.info('Git: %s', line)
        else:
            logging.info('Unexpected Git progress opcode: 0x%x', op_code)

    def line_dropped(self, line):
        logging.info('Git: %s', line)

class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    def __init__(self, repo_name, repo_directory, **kwargs):
        super(Git_Repository, self).__init__(repo_name, repo_directory, **kwargs)
        self.repo = Repo(self.repo_directory)

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
        the logging output.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.
        """

        if progress is True:
            progress = Git_Progress()
        elif progress is False:
            progress = None

        if os.path.exists(repo_directory):
            # Update the repository from the origin URL.
            repository = cls(repo_name, repo_directory, **kwargs)
            repository.repo.remotes.origin.pull('master', progress=progress)
            return repository

        Repo.clone_from(url, repo_directory, progress=progress)
        return cls(repo_name, repo_directory, **kwargs)

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
            'repo_name': str(self.repo_name),
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
