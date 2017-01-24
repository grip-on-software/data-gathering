#!/bin/bash

ROOT=$PWD

# Declare list of projects to scrape from, space-separated
if [ -z "$listOfProjects" ]; then
	listOfProjects="PROJ1 PROJ2 PROJN"
fi

# Declare the tasks to run during the import, comma-separated
if [ -z "$importerTasks" ]; then
	importerTasks="all"
fi

# Files that are backed up in case of errors for each project
restoreFiles="jira-updated.txt git-commit.json history_line_count.txt metric_options_update.json"

function error_handler() {
	echo "Reverting workspace tracking data..."
	for project in $listOfProjects
	do
		for restoreFile in $restoreFiles
		do
			if [ -e "$ROOT/$project/$restoreFile.bak" ]; then
				mv "$ROOT/$project/$restoreFile.bak" "$ROOT/$project/$restoreFile"
			else
				rm -f "$ROOT/$project/$restoreFile"
			fi
		done
	done
}

function status_handler() {
	set +e
	"$@"
	local status=$?
	set -e
	if [ $status -ne 0 ]; then
		echo "[$@] Failed with status code $status" >&2
		error_handler
	fi
	return $status
}

function update_repositories() {
	url=$1
	shift
	listOfRepos=$*
	for repo in $listOfRepos
	do
		# look for empty dir
		if [ "$(ls -A $repo 2>/dev/null)" ]; then
			echo "$repo is not Empty"
			cd "$repo"
			git pull $(printf $url $repo)
			cd ..
		else
			git clone $(printf $url $repo)
		fi
	done
}

# Install Python dependencies
pip install -r scripts/requirements.txt

# Retrieve Python scripts
cp scripts/*.py scripts/*.json scripts/*.cfg .

# Retrieve Java importer
python retrieve_importer.py

## now loop through the list of projects
for project in $listOfProjects
do
	echo "$project"

	# Create backups of tracking files
	for restoreFile in $restoreFiles
	do
		if [ -e "$project/$restoreFile" ]; then
			cp "$project/$restoreFile" "$project/$restoreFile.bak"
		fi
	done

	mkdir -p project-git-repos/$project
	cd project-git-repos/$project
	if [ $project = "PROJ2" ]; then
		listOfRepos="REPO1 REPO2 REPON"
		update_repositories "http://GITLAB_SERVER.localhost/project/%s.git" $listOfRepos
	elif [ $project = "PROJ1" ]; then
		listOfRepos="REPO1 REPO2 REPON"
		update_repositories "http://GITLAB_SERVER.localhost/project/%s" $listOfRepos
	elif [ $project = "PROJ4" ]; then
		listOfRepos="REPO1 REPO2 REPON"
		update_repositories "http://GITLAB_SERVER.localhost/project/%s.git" $listOfRepos
	elif [ $project = "PROJN" ]; then
		listOfRepos="REPO1 REPO2 REPON"
		update_repositories "http://GITLAB_SERVER.localhost/project/%s.git" $listOfRepos
	elif [ $project = "PROJ3" ]; then
		listOfRepos="REPO1 REPO2 REPON"
		update_repositories "http://GITLAB_SERVER.localhost/project/%s.git" $listOfRepos
	fi

	cd ../..
	status_handler python jira_to_json.py $project
	status_handler python git_to_json.py $project
	status_handler python history_to_json.py $project
	status_handler python metric_options_to_json.py $project
	status_handler java -jar importerjson.jar $project $importerTasks
done
