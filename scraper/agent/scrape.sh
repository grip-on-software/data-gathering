#!/bin/sh
chown -R agent:agent /home/agent/export
chown -R agent:agent /home/agent/config
chown -R agent:agent /home/agent/.ssh
chmod -R 600 /home/agent/.ssh
chmod 700 /home/agent/.ssh
/home/agent/scraper/agent/env.sh 'cd /home/agent; set -o pipefail; for key in ${JIRA_KEY}; do mkdir -p /home/agent/export/${key}; set +e; /bin/bash -x /home/agent/scraper/agent/run.sh ${key} "${PREFLIGHT_ARGS}" 2>&1 | tee /home/agent/export/${key}/scrape.log; echo "Process ended with status code $?" >> /home/agent/export/${key}/scrape.log; python /home/agent/scraper/export_files.py ${key} --other /home/agent/export/${key}/scrape.log --log INFO; sleep 10; set -e; done'
