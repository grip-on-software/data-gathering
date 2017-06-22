#!/bin/bash -ex

# Declare the current working directory
ROOT=$PWD

# Declare list of projects to scrape from, space-separated
if [ -z "$listOfProjects" ]; then
	listOfProjects="PROJ1 PROJ2 PROJN"
fi

# The scripts that export data during the gathering
scripts="project_sources.py jira_to_json.py environment_sources.py git_to_json.py history_to_json.py metric_options_to_json.py"

# Declare the script tasks to run during the gathering export, space-separated
if [ -z "$gathererScripts" ]; then
	gathererScripts=$scripts
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

# Declare data gathering skip
if [ -z "$skipGather" ]; then
	skipGather="false"
fi

if [ -z "$IMPORTER_BASE" ]; then
	IMPORTER_BASE="."
fi

# Declare restore files, populated with update files later on
restoreFiles=""
currentProject=""

function error_handler() {
	echo "Reverting workspace tracking data..."
	if [ ! -z "$currentProject" ]; then
		for restoreFile in $restoreFiles
		do
			if [ -e "$ROOT/export/$currentProject/$restoreFile.bak" ]; then
				mv "$ROOT/export/$currentProject/$restoreFile.bak" "$ROOT/export/$currentProject/$restoreFile"
			else
				rm -f "$ROOT/export/$currentProject/$restoreFile"
			fi
		done
	fi
	if [ $cleanupRepos = "true" ]; then
		for project in $listOfProjects
		do
			rm -rf "$ROOT/project-git-repos/$project"
		done
	fi
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

	# Check whether the script should be run according to the environment.
	set +e
	echo $gathererScripts | grep -w -q "\b$script\b"
	local status=$?
	set -e

	if [ $status -ne 0 ]; then
		return
	fi

	# Determine whether to copy a dropin file based on whether this dropin file
	# has already been imported. Also determine whether to actually run the
	# script based on whether the dropin file also has up to date tracker
	# information.
	local skip_dropin=0
	local skip_script=0
	if [ -e "$script.export" ]; then
		skip_dropin=1
		skip_script=1
		if [ -e "$script.update" ]; then
			read -r update_files < "$script.update"
			for update_file in $update_files; do
				set +e
				cmp -s "dropins/$project/$update_file" "export/$project/$update_file"
				local status=$?
				set -e
				if [ "$status" != "0" ]; then
					if [ -e "dropins/$project/$update_file" ]; then
						cp "dropins/$project/$update_file" "export/$project/$update_file"
					elif [ -e "export/$project/$update_file" ]; then
						skip_script=0
					fi
					skip_dropin=0
				fi
			done
		fi

		read -r export_files < "$script.export"
		for export_file in $export_files; do
			if [ -e "dropins/$project/$export_file" ]; then
				if [ "$skip_dropin" = "0" ]; then
					cp "dropins/$project/$export_file" "export/$project/$export_file"
				else
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

# Retrieve Python scripts from a subdirectory
if [ -d scripts ]; then
	cp scripts/*.py scripts/*.py.export scripts/*.py.update scripts/*.json scripts/requirements.txt .
	rm -rf gatherer/
	cp -r scripts/gatherer/ gatherer/
fi

# Install Python dependencies
pip install -r requirements.txt

# Determine files that are backed up in case of errors for each project
restoreFiles=$(./list-files.sh update $gathererScripts)

# Retrieve Java importer
rm -f data_vcsdev_to_dev.json
python retrieve_importer.py --base $IMPORTER_BASE

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
	currentProject=$project

	mkdir -p export/$project
	mkdir -p project-git-repos/$project

	if [ $skipGather = "false" ]; then
		# Retrieve quality metrics repository
		status_handler python retrieve_metrics_repository.py $project --log $logLevel

		status_handler python retrieve_update_trackers.py $project --files $restoreFiles --log $logLevel $trackerParameters
		status_handler python retrieve_dropins.py $project --log $logLevel $dropinParameters

		export_handler project_sources.py $project --log $logLevel
		export_handler jira_to_json.py $project --log $logLevel
		export_handler environment_sources.py $project --log $logLevel
		export_handler git_to_json.py $project --log $logLevel
		export_handler history_to_json.py $project --export-path --export-url --log $logLevel
		export_handler metric_options_to_json.py $project --context -1 --log $logLevel
	fi
	if [ $importerTasks != "skip" ]; then
		status_handler java -Dimporter.log="$logLevel" -Dimporter.update="$restoreFiles" $importerProperties -jar "$IMPORTER_BASE/importerjson.jar" $project $importerTasks
	fi

	if [ $cleanupRepos = "true" ]; then
		rm -rf project-git-repos/$project
	fi
done

if [ $cleanupRepos = "true" ]; then
	python retrieve_metrics_repository.py $project --log $logLevel
fi

# Clean up retrieved dropins
rm -rf dropins

# Clean up duplicated directories
if [ -d scripts ]; then
	rm -rf gatherer
fi
