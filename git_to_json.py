from git import *
import time
import json
import datetime
import pprint

project_repo_folder = "REPO"
project_name = "PROJ1"
data_folder = project_name


json_data=open(project_name+"/data_sprint.json").read()
sprint_data = json.loads(json_data)
sprint_git_data= {}

for sprint in sprint_data:
	sprint_git_data[int(sprint['id'])] = {}
	sprint_git_data[int(sprint['id'])]['start_date'] = datetime.datetime.strptime(sprint['start_date'], '%Y-%m-%d %H:%M:%S')
	sprint_git_data[int(sprint['id'])]['end_date'] = datetime.datetime.strptime(sprint['end_date'], '%Y-%m-%d %H:%M:%S')

repo = Repo("../Project-git-repos/" + project_repo_folder)
o = repo.remotes.origin
o.pull()

skip = 0
iterate_size = 500
iterate_max = 20000

count = 1

git_commit_data = []

commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)
print commits
pp = pprint.PrettyPrinter(indent=4)

while commits and iterate_size + skip <= iterate_max:
	if iterate_size is 0:
		break

	stop_iteration = True

	for commit in commits:
		stop_iteration = False
		git_commit = {}
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


		commit_datetime = datetime.datetime.fromtimestamp(commit.committed_date)
		git_commit['commit_date'] = datetime.datetime.strftime(commit_datetime, '%Y-%m-%d %H:%M:%S')

		for sprint_id in sprint_git_data:
			sprint = sprint_git_data[sprint_id]
			if commit_datetime >= sprint['start_date'] and commit_datetime <= sprint['end_date']:
				git_commit['sprint_id'] = str(sprint_id)
				break
		git_commit_data.append(git_commit)
		#pp.pprint(git_commit)

	print 'Analysed commits up to ',
	print iterate_size+skip

	skip = skip + iterate_size
	if skip + iterate_size > iterate_max:
		iterate_size = iterate_max - skip

	commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)
	#stop iteration if no commits are found in previous round
	if stop_iteration:
		commits = False

#START dump data
with open(data_folder+'/data_commits.json', 'w') as outfile:
	json.dump(git_commit_data, outfile, indent=4)

#END dump data