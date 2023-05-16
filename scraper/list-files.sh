#!/bin/bash

# List files that the gatherer scripts may produce.
# These files may need to be backed up in case of errors, or provided to
# uploaders, exporters or refresh handlers.
# Argument: 'export' or 'update': type of output file.
# Positional arguments: Scripts to consider.
# 
# Copyright 2017-2020 ICTU
# Copyright 2017-2022 Leiden University
# Copyright 2017-2023 Leon Helwerda
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

if [ -z $1 ]; then
	echo "Usage: ./list-files.sh <export|update> [scripts...]"
	exit
fi

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
