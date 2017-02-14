"""
Script used for extracting repository metadata and merge request notes from
a GitLab in order to consolidate this data for later import.
"""

import argparse
from datetime import datetime
import json
import gitlab3

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
        repos[repo] = {
            'info': project_repo._get_data(),
            'merge_requests': [
                mr._get_data() for mr in project_repo.merge_requests()
            ]
        }

    with open(project + '/data_gitlab.json', 'w') as output_file:
        json.dump(repos, output_file, indent=4, default=json_serial)

if __name__ == "__main__":
    main()
