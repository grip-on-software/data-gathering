#!/bin/bash -ex

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

# Declare repository cleanup
if [ -z "$cleanupRepos" ]; then
	cleanupRepos="false"
fi

# Files that are backed up in case of errors for each project
scripts="project_sources.py jira_to_json.py gitlab_to_json.py git_to_json.py history_to_json.py metric_options_to_json.py"
for script in $scripts; do
	if [ -e "$script.update" ]; then
		read -r update_files < "$script.update"
		restoreFiles="$restoreFiles $update_files"
	fi
done

echo $restoreFiles
exit

function error_handler() {
	echo "Reverting workspace tracking data..."
	for project in $listOfProjects
	do
		for restoreFile in $restoreFiles
		do
			if [ -e "$ROOT/export/$project/$restoreFile.bak" ]; then
				mv "$ROOT/export/$project/$restoreFile.bak" "$ROOT/export/$project/$restoreFile"
			else
				rm -f "$ROOT/export/$project/$restoreFile"
			fi
		done
		if [ $cleanupRepos = "true" ]; then
			rm -rf "$ROOT/project-git-repos/$project"
		fi
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

function export_handler() {
	local script=$1
	shift
	local project=$1
	shift
	local args=$*

	local skip_dropin=0
	local skip_script=0
	if [ -e "$script.export" ]; then
		skip_dropin=1
		skip_script=1
		if [ -e "$script.update" ]; then
			read -r update_files < "$script.update"
			for update_file in $update_files; do
				if [ "$(cmp --silent dropins/$project/$update_file export/$project/$update_file)" ]; then
					skip_dropin=0
				fi
			done
		fi

		read -r export_files < "$script.export"
		for export_file in $export_files; do
			if [ -e "dropins/$project/$export_file" ]; then
				if [ "$skip_dropin" = "0" ]; then
					cp "dropins/$project/$export_file" "export/$project/$export_file"
				elif [ "$script" = "git_to_json.py" ]; then
					echo "[]" > export/$project/$export_file
				fi
			else
				skip_script=0
			fi
		done
	fi
	if [ "$skip_script" = "0" ]; then
		status_handler python $script $project $args
	fi
}

# Install Python dependencies
pip install -r scripts/requirements.txt

# Retrieve Python scripts
cp scripts/*.py scripts/*.py.export scripts/*.py.update scripts/*.json scripts/*.cfg .
rm -rf dropins/
rm -rf gatherer/
cp -r scripts/gatherer/ gatherer/
cp -r scripts/dropins/ dropins/

# Retrieve Java importer
python retrieve_importer.py

if [ "$(ls -A kwaliteitsmetingen 2>/dev/null)" ]; then
	cd kwaliteitsmetingen
	svn update -q
	cd ..
else
	svn checkout -q http://SUBVERSION_SERVER.localhost/commons/algemeen/kwaliteitsmetingen/
fi

for project in $listOfProjects
do
	# Create backups of tracking files
	for restoreFile in $restoreFiles
	do
		if [ -e "export/$project/$restoreFile" ]; then
			cp "export/$project/$restoreFile" "export/$project/$restoreFile.bak"
		fi
	done
done

## now loop through the list of projects
for project in $listOfProjects
do
	echo "$project"

	mkdir -p export/$project
	mkdir -p project-git-repos/$project

	export_handler project_sources.py $project --log $logLevel
	export_handler jira_to_json.py $project --log $logLevel
	export_handler gitlab_to_json.py $project --log $logLevel
	export_handler git_to_json.py $project --log $logLevel
	export_handler history_to_json.py $project --export-path --log $logLevel
	export_handler metric_options_to_json.py $project --context -1 --log $logLevel
	status_handler java -Dimporter.log=$logLevel -jar importerjson.jar $project $importerTasks

	if [ $cleanupRepos = "true" ]; then
		rm -rf project-git-repos/$project
	fi
done

if [ $cleanupRepos = "true" ]; then
	rm -rf kwaliteitsmetingen
fi

rm -rf dropins/
rm -rf gatherer/
