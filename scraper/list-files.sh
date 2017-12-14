#!/bin/bash

# List files that the gatherer scripts may produce.
# These files may need to be backed up in case of errors, or provided to
# uploaders, exporters or refresh handlers.
# Argument: 'export' or 'update': type of output file.
# Positional arguments: Scripts to consider.

type=$1
shift
gathererScripts=$*

fileList=""
for script in $gathererScripts; do
	if [ -e "scraper/$script.$type" ]; then
		read -r files < "scraper/$script.$type"
		fileList="$fileList $files"
	fi
done

echo $fileList
