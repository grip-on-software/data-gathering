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
	sprint_git_data[int(sprint['id'])]['commits'] = []
	sprint_git_data[int(sprint['id'])]['commit_count'] = 0


print sprint_git_data

repo = Repo("../Project-git-repos/" + project_repo_folder)
o = repo.remotes.origin
o.pull()

skip = 0
iterate_size = 100
iterate_max = 10000

count = 1

commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)

while commits and iterate_size + skip <= iterate_max:
	if iterate_size is 0:
		break

	for commit in commits:
		commit_datetime = datetime.datetime.fromtimestamp(commit.committed_date)

		for sprint_id in sprint_git_data:
			sprint = sprint_git_data[sprint_id]
			if commit_datetime >= sprint['start_date'] and commit_datetime <= sprint['end_date']:
				sprint['commits'].append(commit)
				sprint['commit_count'] += 1

	skip = skip + iterate_size
	if skip + iterate_size > iterate_max:
		iterate_size = iterate_max - skip

	commits = repo.iter_commits('master', max_count=iterate_size, skip=skip)


#restructure data
sprint_git_data_final = []
for sprint in sprint_git_data:
	sprint_git_data_row = sprint_git_data[sprint]
	sprint_git_data_final_row = {}
	sprint_git_data_final_row['sprint_id'] = sprint
	sprint_git_data_final_row['feature_name'] = 'commit_count'
	sprint_git_data_final_row['user_name'] = 0
	sprint_git_data_final_row['feature_value'] = sprint_git_data_row['commit_count']
	sprint_git_data_final.append(sprint_git_data_final_row)


#prettyprint
#pp = pprint.PrettyPrinter(indent=4)
#pp.pprint(sprint_git_data_final)


#START dump data

with open(data_folder+'/data_git_features.json', 'w') as outfile:
	json.dump(sprint_git_data_final, outfile, indent=4)

#END dump data