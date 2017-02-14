"""
Package for classes related to extracting data from multiple Git repositories.
"""

import json
import os
from datetime import datetime
from git import Repo
from ..utils import parse_unicode, Iterator_Limiter, Sprint_Data
from ..version_control import Version_Control_Repository

__all__ = ["Git_Holder"]

class Git_Holder(object):
    """
    Processor for the various repositories belong to one project.
    """

    def __init__(self, project, repo_directory):
        self.project = project
        self.repo_directory = repo_directory + '/' + self.project
        self.latest_commits = {}
        self.repos = {}
        self.data = []
        self.sprints = Sprint_Data(self.project)

        self.latest_filename = self.project + '/git-commits.json'

    def get_immediate_subdirectories(self):
        """
        Retrieve all the directories of repositories checked out within the
        directory designated for the project repositories.
        """

        return [name for name in os.listdir(self.repo_directory)
                if os.path.isdir(os.path.join(self.repo_directory, name))]

    def get_latest_commits(self):
        """
        Load the information detailing the latest commits from the data store.
        """

        if os.path.exists(self.latest_filename):
            with open(self.latest_filename, 'r') as latest_commits_file:
                self.latest_commits = json.load(latest_commits_file)

        return self.latest_commits

    def get_repositories(self):
        """
        Retrieve repository objects for all repositories.
        """

        repo_names = self.get_immediate_subdirectories()

        for repo_name in repo_names:
            if repo_name in self.latest_commits:
                latest_commit = self.latest_commits[repo_name]
            else:
                latest_commit = None

            repo = Git_Repository(repo_name, self.repo_directory,
                                  latest_commit=latest_commit,
                                  sprints=self.sprints)
            self.repos[repo_name] = repo

        return self.repos

    def process(self):
        """
        Perform all actions required for retrieving the commit data of all
        the repositories and exporting it to JSON.
        """

        self.get_latest_commits()
        self.get_repositories()
        self.parse_repositories()
        self.write_data()

    def parse_repositories(self):
        """
        Load commit data from the repositories after they have been retrieved
        using `get_repositories`.
        """

        for repo_name, repo in self.repos.iteritems():
            print repo_name
            self.data.extend(repo.parse())
            self.latest_commits[repo_name] = repo.latest_commit

    def write_data(self):
        """
        Export the git commit data and latest revision to JSON files, after
        `parse_repositories` has been called.
        """

        with open(self.project + '/data_commits.json', 'w') as data_file:
            json.dump(self.data, data_file, indent=4)

        with open(self.latest_filename, 'w') as latest_commits_file:
            json.dump(self.latest_commits, latest_commits_file)


class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    def __init__(self, repo_name, repo_directory, latest_commit=None, sprints=None):
        super(Git_Repository, self).__init__(repo_name, repo_directory)
        self.repo = Repo(self.repo_directory + '/' + self.repo_name)
        self._latest_commit = latest_commit
        self._sprints = sprints

        self._data = None
        self._iterator_limiter = None
        self._refspec = None
        self._reset_limiter()

    def _reset_limiter(self):
        self._iterator_limiter = Iterator_Limiter()

        # Update refspec
        if self._latest_commit is not None:
            self._refspec = '{}...master'.format(self._latest_commit)
        else:
            self._refspec = 'master'

    @classmethod
    def from_url(cls, repo_name, repo_directory, url):
        """
        Initialize a Git repository from its clone URL if it does not yet exist.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.
        """

        if os.path.exists(repo_directory + '/' + repo_name):
            # Update the repository from the origin URL.
            repository = cls(repo_name, repo_directory)
            repository.repo.remotes.origin.pull('master')
            return repository

        Repo.clone_from(url, repo_directory + '/' + repo_name)
        return cls(repo_name, repo_directory)

    def _query(self, refspec, paths='', descending=True):
        return self.repo.iter_commits(refspec, paths=paths,
                                      max_count=self._iterator_limiter.size,
                                      skip=self._iterator_limiter.skip,
                                      reverse=not descending)

    def parse(self):
        """
        Retrieve commit data from the repository.
        """

        data = self._parse(self._refspec)
        self._latest_commit = self.repo.rev_parse('master').hexsha
        return data

    def get_versions(self, filename='', from_revision=None, to_revision=None, descending=False):
        if from_revision is not None and to_revision is not None:
            refspec = '{}...{}'.format(from_revision, to_revision)
        elif from_revision is not None:
            refspec = '{}...master'.format(from_revision)
        elif to_revision is not None:
            refspec = to_revision
        else:
            refspec = None

        return self._parse(refspec, paths=filename, descending=descending)

    def _parse(self, refspec, paths='', descending=True):
        self._reset_limiter()

        data = []
        commits = self._query(refspec, paths=paths, descending=descending)
        had_commits = True
        while self._iterator_limiter.check(had_commits):
            had_commits = False

            for commit in commits:
                had_commits = True
                data.append(self.parse_commit(commit))

            count = self._iterator_limiter.size + self._iterator_limiter.skip
            print 'Analysed commits up to {}'.format(count)

            self._iterator_limiter.update()

            if self._iterator_limiter.check(had_commits):
                commits = self._query(refspec, paths=paths, descending=descending)

        return data


    def parse_commit(self, commit):
        """
        Convert one commit instance to a dictionary of properties.
        """

        cstotal = commit.stats.total
        commit_datetime = datetime.fromtimestamp(commit.committed_date)

        commit_type = str(commit.type)
        if len(commit.parents) > 1:
            commit_type = 'merge'

        git_commit = {
            # Primary data
            'git_repo': str(self.repo_name),
            'commit_id': str(commit.hexsha),
            'sprint_id': str(0),
            # Statistics
            'insertions': str(cstotal['insertions']),
            'deletions': str(cstotal['deletions']),
            'number_of_files': str(cstotal['files']),
            'number_of_lines': str(cstotal['lines']),
            # More data
            'message': parse_unicode(commit.message),
            'size_of_commit': str(commit.size),
            'type': commit_type,
            'developer': commit.author.name,
            'developer_email': str(commit.author.email),
            'commit_date': datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')
        }

        if self._sprints is not None:
            sprint_id = self._sprints.find_sprint(commit_datetime)
            if sprint_id is not None:
                git_commit['sprint_id'] = str(sprint_id)

        return git_commit

    @property
    def latest_commit(self):
        """
        Retrieve the latest commit date that was collected during `parse`.
        """

        return self._latest_commit
