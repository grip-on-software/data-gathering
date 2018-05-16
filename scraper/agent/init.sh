#!/bin/bash

# Initial Docker entrypoint for the data gathering agent.
# This sets up the environment and jobs to run.
# This script is run as the root user.

if [ ! -z "$CRON_PERIOD" ] && [ "$CRON_PERIOD" != "-" ]; then
	# Enable a cron job for scraping regularly
	cat >/etc/periodic/$CRON_PERIOD/scrape <<'SH'
#!/bin/sh
/home/agent/scraper/agent/scrape.sh
SH

	chmod +x /etc/periodic/$CRON_PERIOD/scrape

	if [ ! -z "$BIGBOAT_PERIOD" ] && [ "$BIGBOAT_PERIOD" != "-" ]; then
		cat >/etc/periodic/$BIGBOAT_PERIOD/bigboat <<'SH'
#!/bin/sh
/home/agent/scraper/agent/env.sh 'cd /home/agent && python scraper/bigboat_to_json.py ${JIRA_KEY}'
SH
		chmod +x /etc/periodic/$BIGBOAT_PERIOD/bigboat
	fi

	crond -b -L /dev/stderr
fi

# Fix any incorrect permissions in the volume
chown -R agent:agent /home/agent/export
find "/home/agent/export" -type d -exec chmod 755 {} \;
find "/home/agent/export" -type f -exec chmod 644 {} \;

# Start the scraper agent within the agent user environment, which performs
# additional environment setup and checks if the scrape should run immediately. 
/home/agent/scraper/agent/env.sh /home/agent/scraper/agent/start.sh
if [ "$?" = "123" ]; then
	# Run a server which keeps the container running until stopped and lets
	# instances in the same network or the host machine send scrape requests.
	echo "Starting docker scraper service"
	python /home/agent/scraper/agent/scraper.py --listen 0.0.0.0
fi
