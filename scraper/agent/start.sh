#!/bin/bash

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
