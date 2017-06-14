#!/bin/bash

AGENTS_DIRECTORY="/agents"
gathererScripts="project_sources.py environment_sources.py git_to_json.py"
updateFiles=$(./list-files.sh update $gathererScripts)

for agent_directory in $AGENTS_DIRECTORY/*; do
	project=${agent_directory##*/}
	controller_directory="/controller/$project/export" 

	sudo chmod 2770 $agent_directory/export
	sudo chmod 2770 $agent_directory/export/$project
	cp -r $agent_directory/export $controller_directory
	sudo rm -rf $agent_directory/export/$project
	sudo mkdir -m 2700 $agent_directory/export/$project
	sudo chmod 2700 $agent_directory/export

	listOfProjects="$project" gathererScripts="$gathererScripts" importerTasks="" logLevel="INFO" skipGather="true" IMPORTER_BASE="." ./jenkins-scraper.sh

	sudo chmod 2770 $agent_directory/update
	sudo chmod 2770 $agent_directory/update/$project
	for updateFile in $updateFiles; do
		updatePath="$controller_directory/$project/$updateFile"
		if [ -e "$updatePath" ]; then
			cp $updatePath $agent_directory/update/$project/$updateFile
		fi
	done
	sudo chmod 2700 $agent_directory/update/$project
	sudo chmod 2700 $agent_directory/update
done
