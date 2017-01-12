import argparse
import time
import json
import pprint
import sys
import os
from datetime import datetime
from git import *
from utils import parse_unicode, Sprint_Data

class Git_Holder(object):
    def __init__(self, project, repo_directory):
        self.project = project
        self.repo_directory = repo_directory + '/' + self.project
        self.latest_commits = {}
        self.repos = {}
        self.data = []
        self.sprints = Sprint_Data(self.project)

        self.latest_filename = self.project + '/git-commits.json'

    def get_immediate_subdirectories(self):
        return [name for name in os.listdir(self.repo_directory)
                if os.path.isdir(os.path.join(self.repo_directory, name))]

    def get_latest_commits(self):
        if os.path.exists(self.latest_filename):
            with open(self.latest_filename, 'r') as latest_commits_file:
                self.latest_commits = json.load(latest_commits_file)

    def get_repositories(self):
        repo_names = self.get_immediate_subdirectories()

        for repo_name in repo_names:
            if repo_name in self.latest_commits:
                latest_commit = self.latest_commits[repo_name]
            else:
                latest_commit = None

            repo = Git_Repository(repo_name, self.repo_directory,
                latest_commit=latest_commit, sprints=self.sprints)
            self.repos[repo_name] = repo

    def process(self):
        self.get_latest_commits()
        self.get_repositories()
        self.parse_repositories()
        self.write_data()

    def parse_repositories(self):
        for repo_name, repo in self.repos.iteritems():
            print repo_name
            repo.parse()
            self.latest_commits[repo_name] = repo.latest_commit
            self.data.extend(repo.data)

    def write_data(self):
        with open(self.project + '/data_commits.json', 'w') as data_file:
            json.dump(self.data, data_file, indent=4)

        with open(self.latest_filename, 'w') as latest_commits_file:
            json.dump(self.latest_commits, latest_commits_file)

class Git_Repository(object):
    def __init__(self, repo_name, repo_directory, latest_commit=None, sprints=None):
        self.repo_name = repo_name
        self.repo = Repo(repo_directory + '/' + self.repo_name)
        self.latest_commit = latest_commit
        self.sprints = sprints

        self.data = []

        self.skip = 0
        self.iterate_size = 1000
        self.iterate_max = 10000000

        if self.latest_commit is not None:
            self.refspec = '{}...master'.format(self.latest_commit)
        else:
            self.refspec = 'master'

    def _query(self):
        return self.repo.iter_commits(self.refspec,
            max_count=self.iterate_size, skip=self.skip
        )

    def parse(self):
        commits = self._query()
        while commits and self.iterate_size + self.skip <= self.iterate_max:
            if self.iterate_size is 0:
                break

            stop_iteration = True

            for commit in commits:
                stop_iteration = False
                self.parse_commit(commit)

            print 'Analysed commits up to {}'.format(self.iterate_size + self.skip)

            self.skip += self.iterate_size
            if self.skip + self.iterate_size > self.iterate_max:
                self.iterate_size = self.iterate_max - self.skip

            commits = self._query()
            #stop iteration if no commits are found in previous round
            if stop_iteration:
                commits = False

        self.latest_commit = self.repo.rev_parse('master').hexsha

    def parse_commit(self, commit):
        cs = commit.stats
        cstotal = cs.total
        commit_datetime = datetime.fromtimestamp(commit.committed_date)

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
            'type': str(commit.type),
            'developer': commit.author.name,
            'developer_email': str(commit.author.email),
            'commit_date': datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')
        }

        sprint_id = self.sprints.find_sprint(commit_datetime)
        if sprint_id is not None:
            git_commit['sprint_id'] = str(sprint_id)

        self.data.append(git_commit)

def parse_args():
    parser = argparse.ArgumentParser(description="Obtain git commit data from project repositories and convert to JSON format readable by the database importer.")
    parser.add_argument("project", help="project key")
    parser.add_argument("--repos", default="project-git-repos", help="directory containing the project repositories")
    return parser.parse_args()

def main():
    args = parse_args()
    project_name = args.project

    holder = Git_Holder(project_name, args.repos)
    holder.process()

if __name__ == "__main__":
    main()
