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
updateFiles=""
exportFiles=""
scripts="project_sources.py git_to_json.py"
for script in $scripts; do
	read -r update_files < "$script.update"
	updateFiles="$updateFiles $update_files"
	read -r export_files < "$script.export"
	exportFiles="$exportFiles $export_files"
done

if [ "$(ls -A kwaliteitsmetingen 2>/dev/null)" ]; then
	cd kwaliteitsmetingen
	svn update -q
	cd ..
else
	svn checkout -q http://SUBVERSION_SERVER.localhost/commons/algemeen/kwaliteitsmetingen/
fi

python retrieve_update_trackers.py $project --files $updateFiles --log $logLevel
python project_sources.py $project --log $logLevel
python environment_sources.py $project --log $logLevel
python git_to_json.py $project --log $logLevel
python export_files.py $project --update $updateFiles --export $exportFiles

if [ $cleanupRepos = "true" ]; then
	rm -rf project-git-repos/$project
	rm -rf kwaliteitsmetingen
fi
