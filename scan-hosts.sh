#!/bin/bash -ex

if [ -z "$HOSTS" ]; then
	HOSTS="$SOURCE_HOST $DEFINITIONS_HOST"
fi

if [ -z "$KNOWN_HOSTS" ]; then
	KNOWN_HOSTS=~/.ssh/known_hosts
fi

for host in $HOSTS; do
	# Remove existing hosts
	if [ -e "$KNOWN_HOSTS" ]; then
		ssh-keygen -R $host -f "$KNOWN_HOSTS"
	fi

	ssh-keyscan $host >> "$KNOWN_HOSTS"
	if [ ! -z "$GITLAB_CREDENTIALS" ]; then
    	# Verify connection and write out known IP as well
    	ssh -i "$GITLAB_CREDENTIALS" git@$host
	fi
done
