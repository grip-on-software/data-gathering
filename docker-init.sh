#!/bin/bash

if [ ! -z "$CRON_PERIOD" ] && [ "$CRON_PERIOD" != "-" ]; then
	# Enable a cron job for scraping regularly
	cat >/etc/periodic/$CRON_PERIOD/scrape <<'SH'
#!/bin/sh
set -o allexport
source /home/agent/env
source /home/agent/config/env
set +o allexport

if [ ! -z "$SOURCE_CREDENTIALS_ENV" ] && [ "$SOURCE_CREDENTIALS_ENV" != "-" ]; then
	export SOURCE_CREDENTIALS_ENV=${SOURCE_CREDENTIALS_ENV}
	export ${SOURCE_CREDENTIALS_ENV}="${!SOURCE_CREDENTIALS_ENV}"
fi
su agent -c 'cd /home/agent && ./docker-scraper.sh ${JIRA_KEY}'
SH

	chmod +x /etc/periodic/$CRON_PERIOD/scrape

	cat >/etc/periodic/15min/bigboat <<'SH'
#!/bin/sh
/home/agent/agent-env.sh 'cd /home/agent && python bigboat_to_json.py ${JIRA_KEY}'
SH
	chmod +x /etc/periodic/15min/bigboat

	crond -b -L /dev/stderr
fi

chown -R agent:agent /home/agent/export
find "/home/agent/export" -type d -exec chmod 755 {} \;
find "/home/agent/export" -type f -exec chmod 644 {} \;

/home/agent/agent-env.sh /home/agent/docker-start.sh
