"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.
"""

from argparse import ArgumentParser, Namespace
import logging

from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Metric_Options_Collector

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain quality metric project definition and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default=None,
                        help="Project definitions repository path or URL")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--from-revision", dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", dest="to_revision", default=None,
                        help="revision to stop gathering definitions at")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key)
    if project.quality_metrics_name is None:
        logging.warning('No metrics options available for %s, skipping.',
                        project_key)
        return

    for source in project.project_definitions_sources:
        try:
            collector = Metric_Options_Collector(project, source,
                                                 repo_path=args.repo,
                                                 context_lines=args.context)
            collector.collect(args.from_revision, args.to_revision)
        except RuntimeError:
            logging.exception('Could not collect metric options of %s',
                              project_key)

if __name__ == "__main__":
    main()
