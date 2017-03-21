"""
Script to obtain version control data from repositories and output JSON readable
by the database importer.
"""

import argparse
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.version_control import Repositories_Holder

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain repository versions and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repos", default="project-git-repos",
                        help="directory containing the project repositories")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project, follow_host_change=args.follow_host_change)

    holder = Repositories_Holder(project, args.repos)
    holder.process()

if __name__ == "__main__":
    main()
