"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.
"""

import argparse
import ConfigParser

from gatherer.project_definition import Metric_Options_Parser
from gatherer.project_definition.metric import Metric_Difference
from gatherer.project_definition.update import Update_Tracker
from gatherer.svn import Subversion_Repository
from gatherer.utils import Project

def parse_svn_revision(rev):
    """
    Convert a Subversion revision number to an integer. Removes the leading 'r'
    if it is present.
    """

    if rev.startswith('r'):
        rev = rev[1:]

    return int(rev)

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain quality metric project definition and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default="kwaliteitsmetingen/trunk",
                        help="Subversion directory with project definitions")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--from-revision", type=parse_svn_revision,
                        dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", type=parse_svn_revision,
                        dest="to_revision", default=None,
                        help="revision to stop gathering definitions at")

    return parser.parse_args()

def process(project, args):
    """
    Perform the revision traversal and project definition parsing.
    """

    update_tracker = Update_Tracker(project.export_key)
    from_revision = update_tracker.get_start_revision(args.from_revision)

    repo = Subversion_Repository('kwaliteitsmetingen', args.repo, stats=False)
    filename = project.quality_metrics_name + '/project_definition.py'
    versions = repo.get_versions(filename, from_revision=from_revision,
                                 to_revision=args.to_revision, descending=False)

    diff = Metric_Difference(project.export_key,
                             update_tracker.get_previous_targets())

    end_revision = None
    for version in versions:
        parser = Metric_Options_Parser(context_lines=args.context,
                                       file_time=version['commit_date'])
        contents = repo.get_contents(filename, revision=version['revision'])
        try:
            parser.load_definition(contents)
            metric_targets = parser.parse()
        except RuntimeError as error:
            print "Problem with revision {}: {}".format(version['revision'], error.message)
            continue

        diff.add_version(version, metric_targets)
        end_revision = version['revision']

    diff.export()

    update_tracker.set_end(end_revision, diff.previous_metric_targets)
    print '{} revisions parsed'.format(len(versions))

def main():
    """
    Main entry point.
    """

    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")
    args = parse_args()

    project_key = args.project
    project = Project(project_key)
    if project.quality_metrics_name is None:
        print 'No quality metrics options available for {}, skipping.'.format(project_key)
        return

    process(project, args)

if __name__ == "__main__":
    main()
