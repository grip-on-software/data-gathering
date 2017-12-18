#!/bin/bash

# Script to move gatherer files from a subdirectory to the current directory

subdir=$1
shift

cp $subdir/*.py $subdir/*.json $subdir/requirements.txt .
rm -rf gatherer/
rm -rf scraper/
cp -r $subdir/gatherer/ gatherer/
cp -r $subdir/scraper/ scraper/
