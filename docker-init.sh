#!/bin/bash

if [ ! -z "$CRON_PERIOD" ]; then
	# Enable a cron job for scraping regularly
	cat >/etc/periodic/$CRON_PERIOD/scrape <<SH
#!/bin/sh
su agent -c /home/agent/docker-scraper.sh ${JIRA_KEY}
SH
	chmod +x /etc/periodic/$CRON_PERIOD/scrape
fi

su agent -c /home/agent/docker-start.sh
