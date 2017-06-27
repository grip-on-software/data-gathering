#!/bin/bash -ex

project=$1;
if [ -z "$project" ]; then
	echo "Project must be provided"
	exit 1
fi

# Declare repository cleanup
if [ -z "$cleanupRepos" ]; then
	cleanupRepos="false"
fi

# Declare log level
if [ -z "$logLevel" ]; then
	logLevel="INFO"
fi

# Declare update and export files
scripts="project_sources.py git_to_json.py"
updateFiles=$(./list-files.sh update $scripts)
exportFiles=$(./list-files.sh export $scripts)

# Remove old update files so that the remote update trackers are always used
for $updateFile in updateFiles; do
	rm -f export/$project/$updateFile
done

python retrieve_metrics_repository.py $project --log $logLevel
python retrieve_update_trackers.py $project --files $updateFiles --log $logLevel
python project_sources.py $project --log $logLevel
python environment_sources.py $project --log $logLevel
python git_to_json.py $project --log $logLevel
python export_files.py $project --update $updateFiles --export $exportFiles

if [ $cleanupRepos = "true" ]; then
	rm -rf project-git-repos/$project
	python retrieve_metrics_repository.py $project --delete --log $logLevel
fi
