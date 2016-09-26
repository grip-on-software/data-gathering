#!/bin/bash

########## Retrieving Settings ###########

project_id='PROJ1'
git_project_id='REPO'

##########################################
echo "Initialising python script for retrieving issues"
python jira_to_json.py $project_id
echo "Creation of issue JSON data is done"
echo "Initialising python script for retrieving git data"
python git_to_json.py $project_id $git_project_id
echo "Creation of git JSON data is done"
echo "Initialising java script for storage"


