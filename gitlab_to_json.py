"""
Script used for extracting repository metadata and merge request notes from
a GitLab in order to consolidate this data for later import.
"""

import argparse
from datetime import datetime
import json
import logging
import os.path
import gitlab3
from gatherer.git import Git_Repository
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

    description = "Gather metadata and merge request notes from repositories"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")
    parser.add_argument("--log-ratio", dest="log_ratio", default=5, type=int,
                        help="Number of lines to sample from Git progress")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

# pylint: disable=no-member
def retrieve_repos(project, log_ratio):
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
    group = api.find_group(name=group_name)
    if not group:
        raise RuntimeError('Could not find group for project group {0}'.format(group_name))

    # Fetch the group projects by requesting the group to the API again
    project_repos = api.group(group.id).projects

    names = ', '.join([repo['name'] for repo in project_repos])
    logging.info('%s has %d repos: %s', group_name, len(project_repos), names)

    repos = {}
    for repo in project_repos:
        project_repo = api.project(repo['id'])
        # Retrieve relevant data from the API.
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

        repo_name = project_repo.name
        repo_dir = 'project-git-repos/{0}/{1}'.format(project.key, repo_name)
        source = Source.from_type('gitlab', name=repo_name,
                                  url=project_repo.http_url_to_repo,
                                  follow_host_change=False)
        git_repo = Git_Repository.from_url(repo_name, repo_dir, source.url,
                                           progress=log_ratio)

        if git_repo.is_empty():
            continue

        if source.url != gitlab_source.url:
            project.add_source(source)

        commits = git_repo.repo.iter_commits('master', remotes=True)
        for commit in commits:
            sha = commit.hexsha
            comments = project_repo.get_comments(sha)
            if comments:
                data['commit_comments'][sha] = {
                    'commit_info': project_repo.commit(sha)._get_data(),
                    'notes': comments
                }
        repos[repo_name] = data

    project.export_sources()

    return repos

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key, follow_host_change=args.follow_host_change)

    repos = retrieve_repos(project, args.log_ratio)

    path = os.path.join(project.export_key, 'data_gitlab.json')
    with open(path, 'w') as output_file:
        json.dump(repos, output_file, indent=4, default=json_serial)

if __name__ == "__main__":
    main()
