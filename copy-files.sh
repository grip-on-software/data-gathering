#!/bin/bash

# Script to move gatherer files from a subdirectory to the current directory

subdir=$1
shift

cp $subdir/*.py $subdir/*.py.export $subdir/*.py.update $subdir/*.json $subdir/requirements.txt $subdir/list-files.sh .
rm -rf gatherer/
cp -r $subdir/gatherer/ gatherer/