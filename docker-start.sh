#!/bin/bash

# Update configuration based on docker compose environment variables.
(find /home/agent -name '*.cfg.example' | while read file; do
	envsubst < $file > ${file%.*}
done)

if [ ! -z "$SSH_HOST" ] && [ "$SSH_HOST" != "-" ]; then
	rm -f /home/agent/.ssh/known_hosts
	ssh-keyscan $SSH_HOST >> /home/agent/.ssh/known_hosts
fi
./scan-hosts.sh

python generate_key.py $JIRA_KEY --gitlab $SOURCE_HOST $DEFINITIONS_HOST
if [ ! -z "$JENKINS_URL" ]; then
	./docker-scraper.sh
else
	# Run a dummy command to keep the container running until stopped
	python -c 'import signal;signal.pause()'
fi
