#!/bin/bash

if [ ! -z "$CRON_PERIOD" ] && [ "$CRON_PERIOD" != "-" ]; then
	# Enable a cron job for scraping regularly
	cat >/etc/periodic/$CRON_PERIOD/scrape <<'SH'
#!/bin/sh
chown -R agent:agent /home/agent/export
chown -R agent:agent /home/agent/config
chown -R agent:agent /home/agent/.ssh
chmod -R 400 /home/agent/.ssh
chmod 700 /home/agent/.ssh
/home/agent/agent-env.sh 'cd /home/agent && ./docker-scraper.sh ${JIRA_KEY}'
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
