"""
Script to obtain attributes and metadata relating to a specific project.
"""

from argparse import ArgumentParser, Namespace
import json
import logging
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Project_Collector

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain project attributes and metadata"
    parser = ArgumentParser(description=description)
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

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project_key = str(args.project)
    project = Project(project_key)

    data = {
        'jira_key': project.jira_key,
        'github_team': project.github_team,
        'gitlab_group_name': project.gitlab_group_name,
        'tfs_collection': project.tfs_collection,
        'quality_name': project.quality_metrics_name,
        'main_project': project.main_project,
        'is_support_team': project.is_support_team
    }

    if project.quality_metrics_name is None:
        logging.warning('No project defintion available for %s, missing out.',
                        project_key)

    for source in project.project_definitions_sources:
        try:
            collector = Project_Collector(project, source, repo_path=args.repo,
                                          context_lines=args.context)
            collector.collect_latest()

            data.update(collector.meta)
        except RuntimeError:
            logging.exception('Could not collect project definition for %s',
                              project_key)

    export_path = project.export_key / 'data_project.json'
    with export_path.open('w') as export_file:
        json.dump(data, export_file)

if __name__ == "__main__":
    main()
