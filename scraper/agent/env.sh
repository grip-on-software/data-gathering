#!/bin/sh -e

if [ -z "$*" ]; then
	command="/bin/bash"
else
	command="$*"
fi

su agent -c "set +e -o allexport; source /home/agent/env; source /home/agent/config/env; set -e +o allexport; $command; exit \$?"
