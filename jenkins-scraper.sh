#!/bin/bash -ex

# Declare the current working directory
ROOT=$PWD

# Declare list of projects to scrape from, space-separated
if [ -z "$listOfProjects" ]; then
	listOfProjects="PROJ1 PROJ2 PROJN"
fi

# The scripts that export data during the gathering
scripts="project_sources.py project_to_json.py jira_to_json.py environment_sources.py git_to_json.py history_to_json.py metric_options_to_json.py jenkins_to_json.py"
# The files that the importer uses
files=""

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

# Declare restore files, populated with update files as scripts are run
restoreFiles=""
# Declare run scripts, populated with script names on the first loop iteration
runScripts=""
# Declare the current project, updated in the main loop
currentProject=""

# Check if an element is in a space-separated list.
# Returns 0 if the element is in the list, and 1 otherwise.
function is_in_list() {
	local element=$1
	shift
	local list=$*

	set +e
	echo $list | grep -w -q "\b$element\b"
	local status=$?
	set -e

	return $status
}

function error_handler() {
	echo "Cleaning up workspace tracking data..."
	if [ ! -z "$currentProject" ]; then
		for restoreFile in $restoreFiles
		do
			rm -f "$ROOT/export/$currentProject/$restoreFile"
		done
	fi
	if [ $cleanupRepos = "true" ]; then
		for project in $listOfProjects
		do
			rm -rf "$ROOT/project-git-repos/$project"
			rm -rf "$ROOT/quality-report-history/$project"
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

	export_files=$(./list-files.sh export $script)
	update_files=$(./list-files.sh update $script)

	# Check whether the script should be run according to the environment or
	# the importers that make use of their data.
	local status=1
	if [ -z "$gathererScripts" ]; then
		for export_file in $export_files; do
			if [ $(is_in_list $export_file $files) ]; then
				status=0
				break
			fi
		done
	else
		status=$(is_in_list $script $gathererScripts)
	fi

	if [ $status -ne 0 ]; then
		# Remove export and update files to ensure that a previous run is not
		# reimported since we did not gather or override them.
		for export_file in $export_files; do
			rm -f "export/$project/$export_file"
		done
		for update_file in $update_files; do
			rm -f "export/$project/$update_file"
		done
		return
	fi

	# Determine whether to copy a dropin file based on whether this dropin file
	# has already been imported. Also determine whether to actually run the
	# script based on whether the dropin file also has up to date tracker
	# information.
	local skip_dropin=0
	local skip_script=0
	if [ ! -z "$export_files" ]; then
		skip_dropin=1
		skip_script=1
		if [ ! -z "$update_files" ]; then
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

		for export_file in $export_files; do
			if [ -e "dropins/$project/$export_file" ]; then
				if [ ! -z "$always_use_dropin" ] || [ "$skip_dropin" = "0" ]; then
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
		if [ ! is_in_list $script $runScripts ]; then
			runScripts="$runScripts $script"
			restoreFiles="$restoreFiles $update_files"
		fi
		# Retrieve trackers for current database state
		status_handler python retrieve_update_trackers.py $project --files $update_files --log $logLevel $trackerParameters

		skip_dropin=$skip_dropin status_handler python $script $project $args
	fi
}

function import_handler() {
	local project=$1
	shift
	local tasks=$*
	status_handler java -Dimporter.log="$logLevel" -Dimporter.update="$restoreFiles" $importerProperties -jar "$IMPORTER_BASE/importerjson.jar" $project $tasks
}

# Retrieve Python scripts from a subdirectory
if [ -d scripts ]; then
	scripts/copy-files.sh scripts
fi

# Install Python dependencies
if [ -z "$SKIP_REQUIREMENTS" ]; then
	pip install -r requirements.txt
fi

# Retrieve Java importer
rm -f data_vcsdev_to_dev.json
python retrieve_importer.py --base $IMPORTER_BASE
if [ -z "$gathererScripts" ] && [ "$importerTasks" != "skip" ]; then
	files=$(import_handler --files $importerTasks)
fi

# Now loop through the list of projects
for project in $listOfProjects
do
	echo "$project"
	currentProject=$project

	mkdir -p export/$project
	mkdir -p project-git-repos/$project

	if [ $skipGather = "false" ]; then
		# Retrieve quality metrics repository
		status_handler python retrieve_metrics_repository.py $project --log $logLevel

		# Retrieve archived project dropins
		status_handler python retrieve_dropins.py $project --log $logLevel $dropinParameters

		always_use_dropin=1 export_handler project_sources.py $project --log $logLevel
		export_handler project_to_json.py $project --log $logLevel
		export_handler jira_to_json.py $project --log $logLevel
		export_handler environment_sources.py $project --log $logLevel
		export_handler git_to_json.py $project --log $logLevel
		export_handler history_to_json.py $project --export-path --export-url --log $logLevel
		export_handler metric_options_to_json.py $project --context -1 --log $logLevel
		export_handler jenkins_to_json.py $project --log $logLevel
	fi
	if [ $importerTasks != "skip" ]; then
		import_handler $project $importerTasks
	fi

	if [ $cleanupRepos = "true" ]; then
		rm -rf project-git-repos/$project
		rm -rf quality-report-history
	fi
done

if [ $cleanupRepos = "true" ]; then
	python retrieve_metrics_repository.py $project --delete --all --log $logLevel
fi

# Clean up retrieved dropins
rm -rf dropins

# Clean up duplicated directories
if [ -d scripts ]; then
	rm -rf gatherer
fi
