"""
Script to obtain git commit data from repositories and output JSON readable
by the database importer.
"""

import argparse
from gatherer.git import Git_Holder

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain git commits from repositories and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repos", default="project-git-repos",
                        help="directory containing the project repositories")
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_name = args.project

    holder = Git_Holder(project_name, args.repos)
    holder.process()

if __name__ == "__main__":
    main()
