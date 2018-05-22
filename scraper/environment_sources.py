"""
Script used for retrieving additional domain sources from environments in
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

    description = "Retrieve additional sources from domain environments"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

# pylint: disable=no-member
def retrieve_sources(project):
    """
    Retrieve sources for a specific project based on environments that contain
    multiple sources with similar traits.
    """

    for environment_source in project.sources.get_environments():
        if environment_source.check_credentials_environment():
            sources = environment_source.get_sources()
            for source in sources:
                # Check if there is already another source with the same URL.
                if project.has_source(source):
                    project.sources.replace(source)
                else:
                    project.sources.add(source)
        else:
            logging.info('Skipping environment %r because it is out of scope',
                         environment_source.environment)

def main():
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key, follow_host_change=args.follow_host_change)

    retrieve_sources(project)
    project.export_sources()

if __name__ == "__main__":
    main()
