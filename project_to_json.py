"""
Script to obtain attributes and metadata relating to a specific project.
"""

import argparse
import json
import os.path
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Project_Collector

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain project attributes and metadata"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default=None,
                        help="Repository directory with project definitions")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    project = Project(project_key)

    data = {
        'jira_key': project.jira_key,
        'github_team': project.github_team,
        'gitlab_group_name': project.gitlab_group_name,
        'quality_name': project.quality_metrics_name,
        'main_project': project.main_project
    }

    collector = Project_Collector(project, repo_path=args.repo,
                                  context_lines=args.context)
    collector.collect_latest()

    data.update(collector.meta)

    export_filename = os.path.join(project.export_key, 'data_project.json')
    with open(export_filename, 'w') as export_file:
        json.dump(data, export_file)

if __name__ == "__main__":
    main()
