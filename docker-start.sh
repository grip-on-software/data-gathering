#!/bin/bash

# Update configuration based on docker compose environment variables.
(find /home/agent -name '*.cfg.example' | while read file; do
	envsubst < $file > ${file%.*}
done)

python generate_key.py $JIRA_KEY
if [ ! -z "$JENKINS_URL" ]; then
	./docker-scraper.sh
else
	# Run a dummy command to keep the container running until stopped
	python -c 'import signal;signal.pause()'
fi