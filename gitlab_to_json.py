"""
Script used for extracting repository metadata and merge request notes from
a GitLab in order to consolidate this data for later import.
"""

import argparse
from datetime import datetime
import json
import os.path
import gitlab3
from gatherer.git import Git_Repository

groups = {
    "PROJ4": {
        "name": "project4",
        "projects": "REPO1 REPO2 REPON".split(' ')
    },
    "PROJ3": {
        "name": "project3",
        "projects": ["REPO1", "REPO2", "REPO3"]
    },
    "PROJ2": {
        "name": "project2",
        "projects": "REPO1 REPO2 REPON".split(' ')
    }
}

url = 'http://GITLAB_SERVER.localhost/'
token = 'TOKEN'

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial

    raise TypeError("Type '{}' not serializable".format(type(obj)))

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Gather metadata and merge request notes from repositories"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = args.project
    project_name = groups[project]["name"]
    project_repos = groups[project]["projects"]

    print '{0}: {1} ({2} repos)'.format(project, project_name, len(project_repos))

    api = gitlab3.GitLab(url, token)

    # pylint: disable=no-member
    repos = {}
    for repo in project_repos:
        project_repo = api.find_project(path_with_namespace='{0}/{1}'.format(project_name, repo))
        data = {
            'info': project_repo._get_data(),
            'merge_requests': [
                {
                    'info': mr._get_data(),
                    'notes': [n._get_data() for n in mr.notes()]
                } for mr in project_repo.merge_requests()
            ],
            'commit_comments': {}
        }

        repo_dir = 'project-git-repos/{0}'.format(project)
        if os.path.exists('{0}/{1}'.format(repo_dir, repo)):
            git_repo = Git_Repository(repo, repo_dir)
            commits = git_repo.repo.iter_commits('master', remotes=True)
            for commit in commits:
                sha = commit.hexsha
                comments = project_repo.get_comments(sha)
                if comments:
                    print(sha)
                    data['commit_comments'][sha] = comments
        else:
            print 'No local clone of the repository, skipping commit comment gathering.'

        repos[repo] = data

    with open(project + '/data_gitlab.json', 'w') as output_file:
        json.dump(repos, output_file, indent=4, default=json_serial)

if __name__ == "__main__":
    main()
