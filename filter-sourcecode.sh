#!/bin/bash -ex

# Declare log level
if [ -z "$logLevel" ]; then
	logLevel="INFO"
fi
if [ -z "$initParams" ]; then
	initParams="--agent"
fi

project=$1
shift

python retrieve_metrics_repository.py $project --log $logLevel
python project_sources.py $project --log $logLevel 
python environment_sources.py $project --log $logLevel

wget -O bfg.jar http://repo1.maven.org/maven2/com/madgag/bfg/1.12.15/bfg-1.12.15.jar
echo 'regex:.==>0' > filter.txt

python init_gitlab.py $project --bfg bfg.jar --filter filter.txt --log $logLevel $initParams --no-user
