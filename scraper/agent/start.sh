#!/bin/bash

# Entry point for the Docker-based data gathering agent.
# 
# Copyright 2017-2020 ICTU
# Copyright 2017-2022 Leiden University
# Copyright 2017-2024 Leon Helwerda
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

# Make the agent version available on the shared config volume.
cp /home/agent/VERSION /home/agent/config/VERSION

# Update configuration based on docker compose environment variables.
(find /home/agent -name '*.cfg.example' | while read file; do
	if [ ! -e "/home/agent/config/$(basename ${file%.*})" ]; then
		envsubst < $file > /home/agent/config/$(basename ${file%.*})
	fi
done)

# Generate keys for the project, if possible.
rm -f /home/agent/.ssh/known_hosts
if [ ! -z "$JIRA_KEY" ] && [ "$JIRA_KEY" != "-" ]; then
	for key in $JIRA_KEY; do
		python scraper/generate_key.py $key --path ${!DEFINITIONS_CREDENTIALS_ENV} --gitlab $SOURCE_HOST $DEFINITIONS_HOST --credentials --log INFO
	done
fi

if [ ! -z "$JENKINS_URL" ]; then
	# Run the scrape immediatately on Jenkins
	for key in $JIRA_KEY; do
		mkdir -p /home/agent/export/$key
		/home/agent/scraper/agent/run.sh $key $PREFLIGHT_ARGS 2>&1 | tee /home/agent/export/$key/scrape.log
	done
else
	exit 123
fi
