#!/bin/sh -e

if [ -z "$*" ]; then
	command="/bin/bash"
else
	command="$*"
fi

su agent -c "source /home/agent/scraper/agent/profile.sh; $command; exit \$?"
