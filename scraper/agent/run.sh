#!/bin/bash -ex

# Script to retrieve data for a project within the data gathering agent and
# export the data to the controller.
# 
# Copyright 2017-2020 ICTU
# Copyright 2017-2022 Leiden University
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
scripts="project_to_json.py project_sources.py git_to_json.py metric_options_to_json.py history_to_json.py jenkins_to_json.py sonar_to_json.py"
preflightFiles=$(./scraper/list-files.sh update preflight.py)
updateFiles=$(./scraper/list-files.sh update $scripts)
exportFiles=$(./scraper/list-files.sh export $scripts)

# Remove old update files so that the remote update trackers are always used.
# This is not the case for preflight_date.txt which is only regenerated locally
# if we can scrape according to the preflight checks.
for updateFile in $updateFiles; do
	rm -f export/$project/$updateFile
done

python scraper/generate_key.py $project --path ${!DEFINITIONS_CREDENTIALS_ENV} --gitlab --source --credentials --log INFO
python scraper/preflight.py $project --log $logLevel $preflightArgs
source /home/agent/scraper/agent/profile.sh export/$project/preflight_env
python scraper/retrieve_metrics_repository.py $project --log $logLevel --force
python scraper/retrieve_update_trackers.py $project --files $updateFiles --log $logLevel
python scraper/project_sources.py $project --log $logLevel
python scraper/project_to_json.py $project --log $logLevel
python scraper/environment_sources.py $project --log $logLevel
python scraper/git_to_json.py $project --log $logLevel --force
python scraper/metric_options_to_json.py $project --log INFO
python scraper/history_to_json.py $project --log INFO
python scraper/jenkins_to_json.py $project --log $logLevel
python scraper/sonar_to_json.py $project --log $logLevel --no-url --metrics ${SONAR_METRICS}
python scraper/export_files.py $project --update $preflightFiles $updateFiles --export $exportFiles

if [ $cleanupRepos = "true" ]; then
	rm -rf project-git-repos/$project
	python scraper/retrieve_metrics_repository.py $project --delete --all --log $logLevel
fi
