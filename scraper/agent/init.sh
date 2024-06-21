#!/bin/bash

# Initial Docker entrypoint for the data gathering agent.
# This sets up the environment and jobs to run.
# This script is run as the root user.
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

# Load environment variables
source /home/agent/scraper/agent/profile.sh
set +e
if [ ! -z "$CRON_PERIOD" ] && [ "$CRON_PERIOD" != "-" ]; then
	# Enable a cron job for scraping regularly
	cat >/etc/periodic/$CRON_PERIOD/scrape <<'SH'
#!/bin/sh
if ! pgrep -f /home/agent/scraper/agent/run.sh > /dev/null; then
	/home/agent/scraper/agent/scrape.sh
fi
SH

	chmod +x /etc/periodic/$CRON_PERIOD/scrape

	if [ ! -z "$BIGBOAT_PERIOD" ] && [ "$BIGBOAT_PERIOD" != "-" ]; then
		cat >/etc/periodic/$BIGBOAT_PERIOD/bigboat <<'SH'
#!/bin/sh
/home/agent/scraper/agent/env.sh 'cd /home/agent && python scraper/bigboat_to_json.py ${JIRA_KEY%% *}'
SH
		chmod +x /etc/periodic/$BIGBOAT_PERIOD/bigboat
	fi

	crond -b -L /dev/stderr
fi

# Fix any incorrect permissions in the volume
chown -R agent:agent /home/agent/export
find "/home/agent/export" -type d -exec chmod 755 {} \;
find "/home/agent/export" -type f -exec chmod 644 {} \;
rm -f /home/agent/export/scrape.log

# Start the scraper agent within the agent user environment, which performs
# additional environment setup and checks if the scrape should run immediately. 
/home/agent/scraper/agent/env.sh /home/agent/scraper/agent/start.sh
if [ "$?" = "123" ]; then
	# Run a server which keeps the container running until stopped and lets
	# instances in the same network or the host machine send scrape requests.
	echo "Starting docker scraper service"
	python /home/agent/scraper/agent/scraper.py --listen 0.0.0.0 --domain $AGENT_HOST
fi
