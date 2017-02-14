"""
Script used for initializing projects on a GitLab in order to prepare an import
of filtered source code into the projects.
"""

import argparse
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

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Initialize repositories for filtered source code storage"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--delete", default=False, action="store_true",
                        help="delete the repositories instead of creating them")
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
    group = api.find_group(name=project_name)
    user = api.find_user(name='jenkins')
    for repo in project_repos:
        if args.delete:
            project_repo = api.find_project(path_with_namespace='{0}/{1}'.format(project_name, repo.lower()))
            if project_repo:
                api.delete_project(project_repo)
                print 'Deleted repository {0}/{1}'.format(project_name, repo)
            else:
                print 'Could not find repository {0}/{1}'.format(project_name, repo)
        else:
            project_repo = api.add_project(repo)
            group.transfer_project(project_repo.id)
            print 'Created repository for {0}/{1}'.format(project_name, repo)

    if group.find_member(id=user.id, access_level=30):
        print 'Jenkins user is already part of the group membership'
    else:
        group.add_member(user.id, 30) # developer
        print 'Added Jenkins user to the group membership'

if __name__ == "__main__":
    main()
