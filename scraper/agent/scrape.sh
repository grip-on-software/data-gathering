#!/bin/sh
chown -R agent:agent /home/agent/export
chown -R agent:agent /home/agent/config
chown -R agent:agent /home/agent/.ssh
chmod -R 600 /home/agent/.ssh
chmod 700 /home/agent/.ssh
/home/agent/scraper/agent/env.sh 'cd /home/agent && /home/agent/scraper/agent/run.sh ${JIRA_KEY} "${PREFLIGHT_ARGS}" 2>&1 | tee /home/agent/export/scrape.log'
/home/agent/scraper/agent/env.sh 'cd /home/agent && python /home/agent/scraper/export_files.py ${JIRA_KEY} --other /home/agent/export/scrape.log --log INFO'
