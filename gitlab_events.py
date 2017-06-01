"""
Script used for extracting repository event streams from a GitLab instance
in order to consolidate this data for later import.
"""

import argparse
from datetime import datetime
import json
import logging
import os.path
import gitlab3
from gitlab3.exceptions import ResourceNotFound
from gatherer.domain import Project
from gatherer.log import Log_Setup

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

    description = "Gather event streams from repositories"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

# pylint: disable=no-member
def retrieve_repos(project):
    """
    Retrieve data from GitLab repositories for a specific project.
    """

    gitlab_source = project.gitlab_source
    if gitlab_source is None:
        logging.warning('Project %s has no GitLab instance with credentials, skipping.',
                        project.key)
        return

    api = gitlab3.GitLab(gitlab_source.host, gitlab_source.gitlab_token)
    group_name = project.gitlab_group_name
    group = api.group(group_name)
    if not group:
        raise RuntimeError('Could not find group for project group {0}'.format(group_name))

    # Fetch the group projects by requesting the group to the API again
    project_repos = api.group(str(group.id)).projects

    names = ', '.join([repo['name'] for repo in project_repos])
    logging.info('%s has %d repos: %s', group_name, len(project_repos), names)

    repos = {}
    for repo_data in project_repos:
        try:
            project_repo = api.project(str(repo_data['id']))
        except ResourceNotFound:
            logging.warning('GitLab repository %s is not accessible',
                            repo_data['name'])
            continue

        repo_name = project_repo.name
        logging.info('Processing GitLab repository %s', repo_name)

        # Retrieve relevant data from the API.
        # pylint: disable=protected-access
        data = {
            'events': [event._get_data() for event in project_repo.events()]
        }

        repos[repo_name] = data

    return repos

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key, follow_host_change=args.follow_host_change)

    repos = retrieve_repos(project)

    path = os.path.join(project.export_key, 'data_gitlabevents.json')
    with open(path, 'w') as output_file:
        json.dump(repos, output_file, indent=4, default=json_serial)

if __name__ == "__main__":
    main()
