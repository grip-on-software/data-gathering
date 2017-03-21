"""
Script used for retrieving additional repositories from a GitLab instance in
order to import data from them later on.
"""

import argparse
from datetime import datetime
import logging
import gitlab3
from gitlab3.exceptions import ResourceNotFound
from gatherer.git import GitLab_Repository
from gatherer.domain import Project, Source
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

    description = "Retrieve additional repositories from a GitLab instance"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")
    parser.add_argument("--log-ratio", dest="log_ratio", type=int,
                        default=GitLab_Repository.DEFAULT_UPDATE_RATIO,
                        help="Number of lines to sample from Git progress")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

# pylint: disable=no-member
def retrieve_repos(project, log_ratio):
    """
    Retrieve GitLab repositories for a specific project.
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

    # Fetch the group projects by requesting the group to the API again.
    project_repos = api.group(group.id).projects

    names = ', '.join([repo['name'] for repo in project_repos])
    logging.info('%s has %d repos: %s', group_name, len(project_repos), names)

    for repo_data in project_repos:
        # Retrieve the actual project from the API, to ensure it is accessible.
        try:
            project_repo = api.project(repo_data['id'])
        except ResourceNotFound:
            logging.warning('GitLab repository %s is not accessible',
                            repo_data['name'])
            continue

        repo_name = project_repo.name
        logging.info('Processing GitLab repository %s', repo_name)

        repo_dir = 'project-git-repos/{0}/{1}'.format(project.key, repo_name)
        source = Source.from_type('gitlab', name=repo_name,
                                  url=project_repo.http_url_to_repo,
                                  follow_host_change=False)
        repo = GitLab_Repository.from_source(source, repo_dir,
                                             progress=log_ratio)

        if repo.is_empty():
            logging.info('Ignoring empty repository %s', repo_name)
            continue

        # Check if there is already another (Git) source with the same URL.
        if all(source.url != existing.url for existing in project.sources):
            project.add_source(source)

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key, follow_host_change=args.follow_host_change)

    retrieve_repos(project, args.log_ratio)
    project.export_sources()

if __name__ == "__main__":
    main()
