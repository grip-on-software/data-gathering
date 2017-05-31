"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import logging

from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.project_definition.svn import Metric_Options_Collector
from gatherer.utils import parse_svn_revision

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = "Obtain quality metric project definition and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default=config.get('definitions', 'path'),
                        help="Subversion directory with project definitions")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--from-revision", type=parse_svn_revision,
                        dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", type=parse_svn_revision,
                        dest="to_revision", default=None,
                        help="revision to stop gathering definitions at")

    Log_Setup.add_argument(parser)
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
    if project.quality_metrics_name is None:
        logging.warning('No metrics options available for %s, skipping.',
                        project_key)
        return

    collector = Metric_Options_Collector(project, args.repo,
                                         context_lines=args.context)
    collector.collect(args.from_revision, args.to_revision)

if __name__ == "__main__":
    main()
