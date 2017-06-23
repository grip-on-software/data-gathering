#!/bin/bash

AGENTS_DIRECTORY="/agents"
CONTROLLER_DIRECTORY="/controller"
gathererScripts="project_sources.py environment_sources.py git_to_json.py"
updateFiles=$(./list-files.sh update $gathererScripts)

for agent_directory in $AGENTS_DIRECTORY/*; do
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
		echo "Skipping import because export directory is empty"
	else
		listOfProjects="$project" gathererScripts="$gathererScripts" importerTasks="vcs,update,developerlink" logLevel="INFO" skipGather="true" IMPORTER_BASE="$CONTROLLER_DIRECTORY" SKIP_REQUIREMENTS="true" importerProperties="-Dimporter.relPath=$project/export" ./jenkins-scraper.sh
	fi

	sudo chmod 2770 $agent_directory/update
	sudo chmod 2770 $agent_directory/update/$project
	sudo rm -rf $agent_directory/update/$project/*
	for updateFile in $updateFiles; do
		updatePath="$controller_directory/export/$project/$updateFile"
		if [ -e "$updatePath" ]; then
			cp $updatePath $agent_directory/update/$project/$updateFile
		fi
	done
	sudo chmod 2700 -R $agent_directory/update/$project
	sudo chmod 2700 $agent_directory/update

	sudo chmod 2700 $agent_directory

	if [ ! -z "$CLEANUP_EXPORT" ]; then
		rm -rf $controller_directory
	fi
done
