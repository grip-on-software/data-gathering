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
	cp -r $agent_directory/export $controller_directory/export
	sudo rm -rf $agent_directory/export/$project
	sudo mkdir -m 2700 $agent_directory/export/$project
	sudo chmod 2700 $agent_directory/export

	if [ -z "$(ls -A $controller_directory/export/$project)" ]; then
		echo "Skipping import because export directory is empty"
	else
		listOfProjects="$project" gathererScripts="$gathererScripts" importerTasks="vcs,update,developerlink" logLevel="INFO" skipGather="true" IMPORTER_BASE="$CONTROLLER_DIRECTORY" importerProperties="-Dimporter.relPath=$project/export" ./jenkins-scraper.sh
	fi

	sudo chmod 2770 $agent_directory/update
	sudo chmod 2770 $agent_directory/update/$project
	for updateFile in $updateFiles; do
		updatePath="$controller_directory/export/$project/$updateFile"
		if [ -e "$updatePath" ]; then
			cp $updatePath $agent_directory/update/$project/$updateFile
		fi
	done
	sudo chmod 2700 $agent_directory/update/$project
	sudo chmod 2700 $agent_directory/update

	sudo chmod 2700 $agent_directory
done
