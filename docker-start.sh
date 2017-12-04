#!/bin/bash

# Update configuration based on docker compose environment variables.
cp /home/agent/VERSION /home/agent/config/VERSION
(find /home/agent -name '*.cfg.example' | while read file; do
	if [ ! -e "/home/agent/config/$(basename ${file%.*})" ]; then
		envsubst < $file > /home/agent/config/$(basename ${file%.*})
	fi
done)

rm -f /home/agent/.ssh/known_hosts
if [ ! -z "$JIRA_KEY" ] && [ "$JIRA_KEY" != "-" ]; then
	python generate_key.py $JIRA_KEY --path ${!DEFINITIONS_CREDENTIALS_ENV} --gitlab $SOURCE_HOST $DEFINITIONS_HOST --credentials --log INFO
fi
if [ ! -z "$JENKINS_URL" ]; then
	# Run the scrape immediatately on Jenkins
	./docker-scraper.sh $JIRA_KEY
else
	exit 123
fi
