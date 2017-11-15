#!/bin/sh

if [ -z "$*" ]; then
	command="/bin/bash"
else
	command="$*"
fi

su agent -c "set -o allexport && source /home/agent/env && source /home/agent/config/env && set +o allexport; $command"

