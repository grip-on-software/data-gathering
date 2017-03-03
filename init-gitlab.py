"""
Script used for initializing projects on a GitLab in order to prepare an import
of filtered source code into the projects.
"""

import argparse
from ConfigParser import RawConfigParser
import logging
import os
import gitlab3
from gatherer.domain import Project
from gatherer.git import Git_Repository
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = RawConfigParser()
    config.read('settings.cfg')

    description = "Initialize repositories for filtered or archived source code storage"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--url", default=config.get('gitlab', 'url'),
                        help="GitLab instance URL to connect with")
    parser.add_argument("--token", default=config.get('gitlab', 'token'),
                        help="GitLab token of group owner or admin")
    parser.add_argument("--repos", default=None, nargs='*',
                        help="repository names to process")

    parser.add_argument("--user", default='jenkins',
                        help="user to add to the group")
    parser.add_argument("--level", default=30, type=int,
                        help="group access level to give to the user")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--delete", default=False, action="store_true",
                       help="delete the repositories instead of creating them")
    group.add_argument("--upload", default=False, action="store_true",
                       help="upload from local repository if it exists")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def delete(api, project, repo_name):
    """
    Delete an existing repository from GitLab if it exists.
    """

    project_name = project.gitlab_group_name
    path = '{0}/{1}'.format(project_name, repo_name.lower())
    project_repo = api.find_project(path_with_namespace=path)
    if project_repo:
        api.delete_project(project_repo)
        logging.info('Deleted repository %s/%s', project_name, repo_name)
    else:
        logging.warning('Could not find repository %s/%s',
                        project_name, repo_name)

def create(api, group, project, repo_name):
    """
    Create a new repository in GitLab if it did not already exist.
    """

    project_name = project.gitlab_group_name
    path = '{0}/{1}'.format(project_name, repo_name.lower())
    project_repo = api.find_project(path_with_namespace=path)
    if project_repo:
        logging.warning('Repository for %s/%s already exists',
                        project_name, repo_name)
    else:
        new_project_repo = api.add_project(repo_name)
        group.transfer_project(new_project_repo.id)
        logging.info('Created repository for %s/%s', project_name, repo_name)

def upload(project, url, repo, repo_name, repo_directory):
    """
    Upload a local repository to the archived repository.
    """

    git = Git_Repository(repo_name, os.path.join(repo_directory, repo))
    if git.exists():
        project_name = project.gitlab_group_name
        url = '{0}{1}/{2}.git'.format(url, project_name, repo_name)
        git.repo.remotes.origin.set_url(url)
        git.repo.remotes.origin.push()
        logging.info('Uploaded local repository to %s', url)
    else:
        logging.warning('Could not find local repository in %s/%s',
                        repo_directory, repo)

def get_git_directories(repo_directory, subdirectory=''):
    """
    Retrieve all immediate directories containing git repositories as well as
    all repositories in subdirectories.
    """

    directories = []
    search_directory = os.path.join(repo_directory, subdirectory)
    for name in os.listdir(search_directory):
        path = os.path.join(search_directory, name)
        if os.path.isdir(path):
            git = Git_Repository(name, path)
            if git.exists():
                directories.append(os.path.join(subdirectory, name))
            elif subdirectory == '':
                directories.extend(get_git_directories(repo_directory,
                                                       subdirectory=name))
            else:
                logging.warning('Giving up on repository candidate %s', path)

    return directories

def update_user(group, user, level):
    """
    Add a user with the correct access level to the group membership.
    """

    if not user:
        logging.warning('No existing user to be added to group membership')
        return

    if group.find_member(id=user.id, access_level=level):
        logging.info('User is already part of the group membership')
    else:
        group.add_member(user.id, level)
        logging.info('Added user to the group membership')

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    project = Project(project_key)
    project_name = project.gitlab_group_name

    repo_directory = os.path.join('project-git-repos', project_key)
    if args.repos:
        project_repos = args.repos
    else:
        project_repos = get_git_directories(repo_directory)

    logging.info('%s: %s (%d repos)',
                 project_key, project_name, len(project_repos))

    api = gitlab3.GitLab(args.url, args.token)

    # pylint: disable=no-member
    group = api.group(project_name)
    user = api.find_user(name=args.user)
    if not group:
        print group
        raise RuntimeError('Group {} not found on GitLab'.format(project_name))

    for repo in project_repos:
        repo_name = repo.replace('/', '-')
        if args.delete:
            delete(api, project, repo_name)
        else:
            create(api, group, project, repo_name)
            if args.upload:
                upload(project, args.url, repo, repo_name, repo_directory)

    update_user(group, user, args.level)

if __name__ == "__main__":
    main()
