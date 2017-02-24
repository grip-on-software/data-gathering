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

# Declare log level
if [ -z "$logLevel" ]; then
	logLevel="INFO"
fi

# Files that are backed up in case of errors for each project
restoreFiles="jira-updated.txt vcs_versions.json history_line_count.txt metric_options_update.json"

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

# Install Python dependencies
pip install -r scripts/requirements.txt

# Retrieve Python scripts
cp scripts/*.py scripts/*.json scripts/*.cfg .
cp -r scripts/gatherer/ gatherer/

# Retrieve Java importer
python retrieve_importer.py

if [ "$(ls -A kwaliteitsmetingen 2>/dev/null)" ]; then
	cd kwaliteitsmetingen
	svn update -q
	cd ..
else
	svn checkout -q http://SUBVERSION_SERVER.localhost/commons/algemeen/kwaliteitsmetingen/
fi

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

	mkdir -p export/$project
	mkdir -p project-git-repos/$project

	status_handler python project_sources.py $project --log $logLevel
	status_handler python jira_to_json.py $project --log $logLevel
	status_handler python gitlab_to_json.py $project --log $logLevel
	status_handler python git_to_json.py $project --log $logLevel
	status_handler python history_to_json.py $project --log $logLevel
	status_handler python metric_options_to_json.py $project --context -1 --log $logLevel
	status_handler java -jar importerjson.jar $project $importerTasks
done
