from git import *
import time
import json
import datetime
import pprint
import sys
import os

project_repo_folder = "REPO"
project_name = "PROJ1"

try:
	if sys.argv[1] is not None:
		project_name = sys.argv[1]
		data_folder = project_name
	if sys.argv[2] is not None:
		project_repo_folder = sys.argv[2]
except IndexError:
	data_folder = project_name

print project_name
print project_repo_folder

def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]


def get_git_data(git_commit_data, project_name, repo_name):
	json_data=open(project_name+"/data_sprint.json").read()
	sprint_data = json.loads(json_data)
	sprint_git_data= {}

	for sprint in sprint_data:
		sprint_git_data[int(sprint['id'])] = {}
		sprint_git_data[int(sprint['id'])]['start_date'] = datetime.datetime.strptime(sprint['start_date'], '%Y-%m-%d %H:%M:%S')
		sprint_git_data[int(sprint['id'])]['end_date'] = datetime.datetime.strptime(sprint['end_date'], '%Y-%m-%d %H:%M:%S')

	repo = Repo("project-git-repos/" + project_name + "/" + repo_name)
	o = repo.remotes.origin
	o.pull()

	skip = 0
	iterate_size = 1000
	iterate_max = 10000000

	commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)

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

			git_commit['message'] = str(commit.message.encode('utf-8'))
			git_commit['size_of_commit'] = str(commit.size)
			git_commit['type'] = str(commit.type)
			git_commit['developer'] = str(commit.author.name)
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

		commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)
		#stop iteration if no commits are found in previous round
		if stop_iteration:
			commits = False

		return git_commit_data


git_commit_data = []
repos = get_immediate_subdirectories("project-git-repos/" + project_name)
for repo_name in repos:
	print repo_name
	git_commit_data = get_git_data(git_commit_data, project_name, repo_name)

#START dump data
with open(data_folder+'/data_commits.json', 'w') as outfile:
	json.dump(git_commit_data, outfile, indent=4)

#END dump data