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
	python scraper/generate_key.py $JIRA_KEY --path ${!DEFINITIONS_CREDENTIALS_ENV} --gitlab $SOURCE_HOST $DEFINITIONS_HOST --credentials --log INFO
fi

if [ ! -z "$JENKINS_URL" ]; then
	# Run the scrape immediatately on Jenkins
	/home/agent/scraper/agent/run.sh $JIRA_KEY 2>&1 | tee /home/agent/export/scrape.log
else
	exit 123
fi
