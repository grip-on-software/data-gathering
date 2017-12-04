#!/bin/bash -ex

project=$1;
if [ -z "$project" ] || [ "$project" == "-" ]; then
	echo "Project must be provided"
	exit 1
fi
preflightArgs=$2;

# Declare repository cleanup
if [ -z "$cleanupRepos" ]; then
	cleanupRepos="false"
fi

# Declare log level
if [ -z "$logLevel" ]; then
	logLevel="INFO"
fi

# Declare update and export files
scripts="project_to_json.py project_sources.py git_to_json.py jenkins_to_json.py"
preflightFiles=$(./list-files.sh update preflight.py)
updateFiles=$(./list-files.sh update $scripts)
exportFiles=$(./list-files.sh export $scripts)

# Remove old update files so that the remote update trackers are always used
for updateFile in $updateFiles; do
	rm -f export/$project/$updateFile
done
for preflightFile in $preflightFiles; do
	rm -f export/$project/$preflightFile
done

python generate_key.py $project --path ${!DEFINITIONS_CREDENTIALS_ENV} --gitlab --source --credentials --log INFO
python preflight.py $project --log $logLevel $preflightArgs
python retrieve_metrics_repository.py $project --log $logLevel
python retrieve_update_trackers.py $project --files $updateFiles --log $logLevel
python project_sources.py $project --log $logLevel
python project_to_json.py $project --log $logLevel
python environment_sources.py $project --log $logLevel
python git_to_json.py $project --log $logLevel
python jenkins_to_json.py $project --log $logLevel
python export_files.py $project --update $preflightFiles $updateFiles --export $exportFiles

if [ $cleanupRepos = "true" ]; then
	rm -rf project-git-repos/$project
	python retrieve_metrics_repository.py $project --delete --all --log $logLevel
fi
