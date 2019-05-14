#!/bin/bash

AGENTS_DIRECTORY="/agents"
CONTROLLER_DIRECTORY="/controller"
# The scripts that the agent scraper runs which generate update files
gathererScripts="preflight.py project_to_json.py project_sources.py environment_sources.py git_to_json.py jenkins_to_json.py sonar_to_json.py"
updateFiles=$(./scraper/list-files.sh update $gathererScripts)
preflightFiles=$(./scraper/list-files.sh update preflight.py)

perform_export() {
	agent_directory=$1
	shift
	project=$1
	shift
	controller_directory="$CONTROLLER_DIRECTORY/$project"

	sudo chmod 2770 "$agent_directory"

	sudo chmod 2770 "$agent_directory/export"
	sudo chmod 2770 "$agent_directory/export/$project"
	if [ ! -e "$controller_directory/export/$project" ]; then
		mkdir -p "$controller_directory/export/$project"
		chmod 770 "$controller_directory"
		chmod 770 "$controller_directory/export"
		chmod 770 "$controller_directory/export/$project"
	fi
	cp -r "$agent_directory/export/$project" "$controller_directory/export/$project"
	sudo rm -rf $agent_directory/export/$project/*

	touch "$controller_directory/log.json"
	if [ -e "$controller_directory/export/$project/scrape.log" ]; then
		mv "$controller_directory/export/$project/scrape.log" "$controller_directory/scrape.log"
	fi

	if [ -z "$(ls -A $controller_directory/export/$project)" ]; then
		echo "Skipping import of $project because export directory is empty"
	else
		echo "Preparing to import $project when no other tasks are running"
		while pgrep -u $USER -f "jenkins\.sh" > /dev/null; do
			sleep 1
		done
		listOfProjects="$project" gathererScripts="$gathererScripts" importerTasks="vcs,environment,jenkins,metric_value,update,developerlink,repo_sources" logLevel="INFO" skipGather="true" restoreFiles="$updateFiles" IMPORTER_BASE="$CONTROLLER_DIRECTORY" relPath="$project/export" SKIP_REQUIREMENTS="true" ./scraper/jenkins.sh 2>&1 | tee "$controller_directory/export.log"
		local status=$?

		if [ $status -eq 0 ]; then
			sudo chmod 2770 "$agent_directory/update"
			sudo chmod 2770 "$agent_directory/update/$project"
			sudo rm -rf $agent_directory/update/$project/*
			for updateFile in $updateFiles; do
				updatePath="$controller_directory/export/$project/$updateFile"
				if [ -e "$updatePath" ]; then
					cp "$updatePath" "$agent_directory/update/$project/$updateFile"
				else
					echo "Update file $updatePath could not be copied"
				fi
			done
			# Do not push back preflight update file to agent
			for preflightFile in $preflightFiles; do
				rm -f "$agent_directory/update/$project/$preflightFile"
			done
			sudo chown agent-$project:controller -R "$agent_directory/update/$project"
			sudo chmod 2770 $agent_directory/update/$project
			sudo chmod 2770 $agent_directory/update
		fi
	fi

	sudo chmod 2770 $agent_directory

	if [ ! -z "$CLEANUP_EXPORT" ]; then
		rm -rf $controller_directory/export
	fi
}

directory=$1
project=$2
if [ -z $directory ]; then
	for agent_directory in $AGENTS_DIRECTORY/*; do
		project=${agent_directory##*/}
		perform_export $agent_directory $project
	done
else
	perform_export $directory $project
fi
