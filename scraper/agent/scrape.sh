#!/bin/sh

# Script to perform a complete data gathering of the projects that the agent is
# configured to collect.
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

# Correct ownership and permissions
chown -R agent:agent /home/agent/export
chown -R agent:agent /home/agent/config
chown -R agent:agent /home/agent/.ssh
chmod -R 600 /home/agent/.ssh
chmod 700 /home/agent/.ssh

/home/agent/scraper/agent/env.sh 'cd /home/agent; set -o pipefail; for key in ${JIRA_KEY}; do mkdir -p /home/agent/export/${key}; set +e; /bin/bash -ex /home/agent/scraper/agent/run.sh ${key} "${PREFLIGHT_ARGS}" 2>&1 | tee /home/agent/export/${key}/scrape.log; echo "Process ended with status code $?" >> /home/agent/export/${key}/scrape.log; python /home/agent/scraper/export_files.py ${key} --other /home/agent/export/${key}/scrape.log --log INFO; sleep 10; set -e; done'
