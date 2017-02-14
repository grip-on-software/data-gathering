"""
Script used for initializing projects on a GitLab in order to prepare an import
of filtered source code into the projects.
"""

import sys
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

def main():
    """
    Main entry point.
    """

    project = sys.argv[1]
    project_name = groups[project]["name"]
    project_repos = groups[project]["projects"]

    print '{0}: {1} ({2} repos)'.format(project, project_name, len(project_repos))

    api = gitlab3.GitLab(url, token)

    # pylint: disable=no-member
    group = api.find_group(name=project_name)
    user = api.find_user(name='jenkins')
    for repo in project_repos:
        project_repo = api.add_project(repo)
        group.transfer_project(project_repo.id)
        print 'Created repository for {0}/{1}'.format(project_name, repo)

    group.add_member(user.id, 30) # developer
    print 'Added Jenkins user to the group membership'

if __name__ == "__main__":
    main()
