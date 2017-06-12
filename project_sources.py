"""
Script to parse current project definitions and extract metric sources from
the products and components.
"""

from builtins import str
import argparse
import logging

from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Sources_Collector
from gatherer.domain import Project

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain project sources definition"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default="kwaliteitsmetingen/trunk",
                        help="Subversion directory with project definitions")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--all", action="store_true", default=False,
                        help="retrieve all updated versions of the definition")
    parser.add_argument("--from-revision", dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", dest="to_revision", default=None,
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

    project_name = project.quality_metrics_name
    if project_name is None:
        if project.main_project is not None:
            reason = 'main project is {}'.format(project.main_project)
        else:
            reason = 'no long name or main project defined'

        logging.warning('No project sources available for %s (%s), skipping.',
                        project_key, reason)
        project.export_sources()
        return

    collector = Sources_Collector(project, args.repo,
                                  context_lines=args.context)
    if args.all or args.from_revision is not None or args.to_revision is not None:
        collector.collect(args.from_revision, args.to_revision)
    else:
        latest_version = str(collector.repo.get_latest_version())
        collector.collect_version({'version_id': latest_version})
        collector.finish(latest_version)

    project.export_sources()

if __name__ == "__main__":
    main()
