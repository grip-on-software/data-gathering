#!/bin/sh
if [ ! -z "$1" ]; then
	FILES=$1
else
	FILES="/home/agent/env /home/agent/config/env"
fi

set +e -o allexport
for file in $FILES; do
	source "$file"
done
set -e +o allexport
