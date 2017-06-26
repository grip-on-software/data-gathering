#!/bin/bash

if [ ! -z "$CRON_PERIOD" ] && [ "$CRON_PERIOD" != "-" ]; then
	# Enable a cron job for scraping regularly
	if [ ! -z "$SOURCE_CREDENTIALS_ENV" ] && [ "$SOURCE_CREDENTIALS_ENV" != "-" ]; then
		cat >/etc/periodic/$CRON_PERIOD/scrape <<SH
#!/bin/sh
export SOURCE_CREDENTIALS_ENV=${SOURCE_CREDENTIALS_ENV}
export ${SOURCE_CREDENTIALS_ENV}="${!SOURCE_CREDENTIALS_ENV}"
su agent -c 'cd /home/agent && ./docker-scraper.sh ${JIRA_KEY}'
SH
	else
		cat >/etc/periodic/$CRON_PERIOD/scrape <<SH
#!/bin/sh
su agent -c 'cd /home/agent && ./docker-scraper.sh ${JIRA_KEY}'
SH
	fi

	chmod +x /etc/periodic/$CRON_PERIOD/scrape

	cat >/etc/periodic/15min/bigboat <<SH
#!/bin/sh
su agent -c 'cd /home/agent && python bigboat_to_json.py ${JIRA_KEY}'
SH
	chmod +x /etc/periodic/15min/bigboat

	crond -b -L /dev/stderr
fi

su agent -c /home/agent/docker-start.sh
