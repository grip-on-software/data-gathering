#!/bin/bash

AGENTS_DIRECTORY="/agents"
CONTROLLER_DIRECTORY="/controller"
gathererScripts="project_sources.py environment_sources.py git_to_json.py jenkins_to_json.py"
updateFiles=$(./list-files.sh update $gathererScripts)

perform_export() {
	agent_directory=$1
	shift
	project=${agent_directory##*/}
	controller_directory="$CONTROLLER_DIRECTORY/$project"

	sudo chmod 2770 $agent_directory

	sudo chmod 2770 $agent_directory/export
	sudo chmod 2770 $agent_directory/export/$project
	if [ ! -e "$controller_directory" ]; then
		mkdir -m 770 $controller_directory
	fi
	cp -r $agent_directory/export $controller_directory
	sudo rm -rf $agent_directory/export/$project/*

	if [ -z "$(ls -A $controller_directory/export/$project)" ]; then
		echo "Skipping import of $project because export directory is empty"
	else
		echo "Preparing to import $project when no other tasks are running"
		while pgrep -u $USER jenkins_scraper.sh > /dev/null; do
			sleep 1
		done
		listOfProjects="$project" gathererScripts="$gathererScripts" importerTasks="vcs,jenkins,update,developerlink" logLevel="INFO" skipGather="true" IMPORTER_BASE="$CONTROLLER_DIRECTORY" SKIP_REQUIREMENTS="true" importerProperties="-Dimporter.relPath=$project/export" ./jenkins-scraper.sh
		local status=$?

		if [ $status -eq 0 ]; then
			sudo chmod 2770 $agent_directory/update
			sudo chmod 2770 $agent_directory/update/$project
			sudo rm -rf $agent_directory/update/$project/*
			for updateFile in $updateFiles; do
				updatePath="$controller_directory/export/$project/$updateFile"
				if [ -e "$updatePath" ]; then
					cp $updatePath $agent_directory/update/$project/$updateFile
				else
					echo "Update file $updatePath could not be copied"
				fi
			done
			sudo chown agent-$project:controller -R $agent_directory/update/$project
			sudo chmod 2700 $agent_directory/update/$project
			sudo chmod 2700 $agent_directory/update
		fi
	fi

	sudo chmod 2700 $agent_directory

	if [ ! -z "$CLEANUP_EXPORT" ]; then
		rm -rf $controller_directory/export
	fi
}

directory=$1
if [ -z $directory ]; then
	for agent_directory in $AGENTS_DIRECTORY/*; do
		perform_export $agent_directory
	done
else
	perform_export $directory
fi
