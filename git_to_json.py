from git import *
import argparse
import time
import json
import datetime
import pprint
import sys
import os

def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]

def get_git_data(git_commit_data, latest_commits, project_name, repo_name):
    json_data=open(project_name+"/data_sprint.json").read()
    sprint_data = json.loads(json_data)
    sprint_git_data= {}

    for sprint in sprint_data:
        sprint_git_data[int(sprint['id'])] = {}
        sprint_git_data[int(sprint['id'])]['start_date'] = datetime.datetime.strptime(sprint['start_date'], '%Y-%m-%d %H:%M:%S')
        sprint_git_data[int(sprint['id'])]['end_date'] = datetime.datetime.strptime(sprint['end_date'], '%Y-%m-%d %H:%M:%S')

    repo = Repo("project-git-repos/" + project_name + "/" + repo_name)
    o = repo.remotes.origin
    #o.pull()

    skip = 0
    iterate_size = 1000
    iterate_max = 10000000

    if repo_name in latest_commits:
        refspec = '{}...master'.format(latest_commits[repo_name])
    else:
        refspec = 'master'

    commits = repo.iter_commits(refspec, max_count=iterate_size, skip=skip)

    while commits and iterate_size + skip <= iterate_max:
        if iterate_size is 0:
            break

        stop_iteration = True

        for commit in commits:
            stop_iteration = False
            git_commit = {}
            git_commit['git_repo'] = str(repo_name)
            git_commit['commit_id'] = str(commit.hexsha)
            git_commit['sprint_id'] = str(0)

            cs = commit.stats
            cstotal = cs.total

            git_commit['insertions'] = str(cstotal['insertions'])
            git_commit['deletions'] = str(cstotal['deletions'])
            git_commit['number_of_files'] = str(cstotal['files'])
            git_commit['number_of_lines'] = str(cstotal['lines'])

            git_commit['message'] = commit.message.encode('utf-8')
            git_commit['size_of_commit'] = str(commit.size)
            git_commit['type'] = str(commit.type)
            git_commit['developer'] = commit.author.name
            git_commit['developer_email'] = str(commit.author.email)

            commit_datetime = datetime.datetime.fromtimestamp(commit.committed_date)
            git_commit['commit_date'] = datetime.datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')

            for sprint_id in sprint_git_data:
                sprint = sprint_git_data[sprint_id]
                if commit_datetime >= sprint['start_date'] and commit_datetime <= sprint['end_date']:
                    git_commit['sprint_id'] = str(sprint_id)
                    break

            git_commit_data.append(git_commit)

        print 'Analysed commits up to ',
        print iterate_size+skip

        skip = skip + iterate_size
        if skip + iterate_size > iterate_max:
            iterate_size = iterate_max - skip

        commits = repo.iter_commits(refspec, max_count=iterate_size, skip=skip)
        #stop iteration if no commits are found in previous round
        if stop_iteration:
            commits = False

    latest_commit = repo.rev_parse('master')
    latest_commits[repo_name] = latest_commit.hexsha

def parse_args():
    parser = argparse.ArgumentParser(description="Obtain git commit data from project repositories and convert to JSON format readable by the database importer.")
    parser.add_argument("project", help="project key")
    return parser.parse_args()

def main():
    args = parse_args()
    project_name = args.project
    data_folder = project_name

    latest_commits = {}
    latest_filename = data_folder + '/git-commits.json'
    if os.path.exists(latest_filename):
        with open(latest_filename, 'r') as latest_commits_file:
            latests_commits = json.load(latest_commits_file)

    git_commit_data = []
    repos = get_immediate_subdirectories("project-git-repos/" + project_name)
    for repo_name in repos:
        print repo_name
        get_git_data(git_commit_data, latest_commits, project_name, repo_name)

    #START dump data
    with open(data_folder + '/data_commits.json', 'w') as outfile:
        json.dump(git_commit_data, outfile, indent=4)

    with open(latest_filename, 'w') as latest_commits_file:
        json.dump(latest_commits, latest_commits_file)

    #END dump data

if __name__ == "__main__":
    main()
