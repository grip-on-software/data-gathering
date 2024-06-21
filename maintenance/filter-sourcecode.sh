#!/bin/bash -ex

# Script to retrieve and filter code repositories of a project so that it is
# unintelligible but can still be used for some code size metrics like LOC.
#
# Copyright 2017-2020 ICTU
# Copyright 2017-2022 Leiden University
# Copyright 2017-2024 Leon Helwerda
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
 
# Declare log level
if [ -z "$logLevel" ]; then
	logLevel="INFO"
fi
if [ -z "$initParams" ]; then
	initParams="--agent"
fi

if [ -z $1 ]; then
	echo "Usage: ./maintenance/filter-sourcecode.sh <projectKey>"
	exit
fi

project=$1
shift

python scraper/retrieve_metrics_repository.py $project --log $logLevel
python scraper/project_sources.py $project --log $logLevel 
python scraper/environment_sources.py $project --log $logLevel

wget -O bfg.jar http://repo1.maven.org/maven2/com/madgag/bfg/1.12.15/bfg-1.12.15.jar
echo 'regex:.==>0' > filter.txt

python maintenance/init_gitlab.py $project --bfg bfg.jar --filter filter.txt --log $logLevel $initParams --no-user
