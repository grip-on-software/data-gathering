"""
Script used for retrieving additional repositories from a GitLab instance in
order to import data from them later on.
"""

import argparse
import logging
from gatherer.domain import Project
from gatherer.log import Log_Setup

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

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

# pylint: disable=no-member
def retrieve_repos(project):
    """
    Retrieve GitLab repositories for a specific project.
    """

    gitlab_source = project.gitlab_source
    if gitlab_source is None:
        logging.warning('Project %s has no GitLab instance with credentials, skipping.',
                        project.key)
        return

    sources = gitlab_source.get_sources()
    for source in sources:
        # Check if there is already another (Git) source with the same URL.
        if not project.has_source(source):
            project.add_source(source)

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key, follow_host_change=args.follow_host_change)

    retrieve_repos(project)
    project.export_sources()

if __name__ == "__main__":
    main()
