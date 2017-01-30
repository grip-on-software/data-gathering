"""
Script to obtain git commit data from repositories and output JSON readable
by the database importer.
"""

import argparse
import json
import os
from datetime import datetime
from git import Repo
from utils import parse_unicode, Sprint_Data

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
            repo.parse()
            self.latest_commits[repo_name] = repo.latest_commit
            self.data.extend(repo.data)

    def write_data(self):
        """
        Export the git commit data and latest revision to JSON files, after
        `parse_repositories` has been called.
        """

        with open(self.project + '/data_commits.json', 'w') as data_file:
            json.dump(self.data, data_file, indent=4)

        with open(self.latest_filename, 'w') as latest_commits_file:
            json.dump(self.latest_commits, latest_commits_file)

class Iterator_Limiter(object):
    """
    Class which keeps handles batches of queries and keeps track of iterator
    count, in order to limit batch processing.
    """

    def __init__(self):
        self._skip = 0
        self._size = 1000
        self._max = 10000000

    def check(self, had_commits):
        """
        Check whether a loop condition to continue retrieving iterator data
        should still evaluate to true.
        """

        if had_commits and self._size != 0 and not self.reached_limit():
            return True

        return False

    def reached_limit(self):
        """
        Check whether the hard limit of the iterator limiter has been reached.
        """

        if self._skip + self._size > self._max:
            return True

        return False

    def update(self):
        """
        Update the iterator counter after a batch, to prepare the next query.
        """

        self._skip += self._size
        if self.reached_limit():
            self._size = self._max - self._skip

    @property
    def size(self):
        """
        Retrieve the size of the next batch query.
        """

        return self._size

    @property
    def skip(self):
        """
        Retrieve the current iterator counter.
        """

        return self._skip

class Git_Repository(object):
    """
    A single Git repository that has commit data that can be read.
    """

    def __init__(self, repo_name, repo_directory, latest_commit=None, sprints=None):
        self.repo_name = repo_name
        self.repo = Repo(repo_directory + '/' + self.repo_name)
        self.latest_commit = latest_commit
        self.sprints = sprints

        self._data = []

        self.iterator_limiter = Iterator_Limiter()

        if self.latest_commit is not None:
            self.refspec = '{}...master'.format(self.latest_commit)
        else:
            self.refspec = 'master'

    def _query(self):
        return self.repo.iter_commits(self.refspec,
                                      max_count=self.iterator_limiter.size,
                                      skip=self.iterator_limiter.skip)

    def parse(self):
        """
        Retrieve commit data from the repository.
        """

        commits = self._query()
        had_commits = True
        while self.iterator_limiter.check(had_commits):
            had_commits = False

            for commit in commits:
                had_commits = True
                self.parse_commit(commit)

            count = self.iterator_limiter.size + self.iterator_limiter.skip
            print 'Analysed commits up to {}'.format(count)

            self.iterator_limiter.update()

            if self.iterator_limiter.check(had_commits):
                commits = self._query()

        self.latest_commit = self.repo.rev_parse('master').hexsha

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

        sprint_id = self.sprints.find_sprint(commit_datetime)
        if sprint_id is not None:
            git_commit['sprint_id'] = str(sprint_id)

        self._data.append(git_commit)

    @property
    def data(self):
        """
        Retrieve the commit data from this repository, after `parse` has been
        called.
        """

        return self._data

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain git commits from repositories and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repos", default="project-git-repos",
                        help="directory containing the project repositories")
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_name = args.project

    holder = Git_Holder(project_name, args.repos)
    holder.process()

if __name__ == "__main__":
    main()
