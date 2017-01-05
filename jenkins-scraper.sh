#!/bin/bash
pip install jira
pip install gitpython
pip install requests

cp scripts/jira_to_json.py jira_to_json.py
cp scripts/git_to_json.py git_to_json.py
cp scripts/history_to_json.py history_to_json.py
cp scripts/importerjson.jar importerjson.jar
cp -r scripts/lib lib

## declare an array variable
listOfProjects="PROJ1 PROJ2 PROJN"

## now loop through the above array
for project in $listOfProjects
do
   echo "$project"
   mkdir -p project-git-repos/$project
   cd project-git-repos/$project
   if [ $project = "PROJ2" ]; then
      listOfRepos="REPO1 REPO2 REPON"
      for repo in $listOfRepos
      do
         # look for empty dir
         if [ "$(ls -A $repo)" ]; then
            echo "$repo is not Empty"
            cd "$repo"
            git pull http://GITLAB_SERVER.localhost/project/"$repo".git
            cd ..
         else
            git clone http://GITLAB_SERVER.localhost/project/"$repo".git
         fi
      done
   elif [ $project = "PROJ1" ]; then
      listOfRepos="REPO1 REPO2 REPON"
      for repo in $listOfRepos
      do
         # look for empty dir
         if [ "$(ls -A $repo)" ]; then
            echo "$repo is not Empty"
            cd "$repo"
            git pull http://GITLAB_SERVER.localhost/project/"$repo"
            cd ..
         else
            git clone http://GITLAB_SERVER.localhost/project/"$repo"
         fi
      done
   elif [ $project = "PROJ4" ]; then
      listOfRepos="REPO1 REPO2 REPON"
      for repo in $listOfRepos
      do
         # look for empty dir
         if [ "$(ls -A $repo)" ]; then
            echo "$repo is not Empty"
            cd "$repo"
            git pull http://GITLAB_SERVER.localhost/project/"$repo".git
            cd ..
         else
            git clone http://GITLAB_SERVER.localhost/project/"$repo".git
         fi
      done
   elif [ $project = "PROJN" ]; then
      listOfRepos="REPO1 REPO2 REPON"
      for repo in $listOfRepos
      do
         # look for empty dir
         if [ "$(ls -A $repo)" ]; then
            echo "$repo is not Empty"
            cd "$repo"
            git pull http://GITLAB_SERVER.localhost/project/"$repo".git
            cd ..
         else
            git clone http://GITLAB_SERVER.localhost/project/"$repo".git
         fi
      done
   elif [ $project = "PROJ3" ]; then
      listOfRepos="REPO1 REPO2 REPON"
      for repo in $listOfRepos
      do
         # look for empty dir
         if [ "$(ls -A $repo)" ]; then
            echo "$repo is not Empty"
            cd "$repo"
            git pull http://GITLAB_SERVER.localhost/project/"$repo".git
            cd ..
         else
            git clone http://GITLAB_SERVER.localhost/project/"$repo".git
         fi
      done
   fi

   cd ../..
   python jira_to_json.py $project
   python git_to_json.py $project
   python history_to_json.py $project
   java -jar importerjson.jar $project
done
