"""
Script to retrieve JIRA issue data and convert it to JSON format readable by
the database importer.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import configparser
from gatherer.jira import Jira, Updated_Time, Update_Tracker
from gatherer.log import Log_Setup
from gatherer.domain import Project

def validate_date(value):
    """
    Check whether a given value can be correctly parsed as a timestamp with
    a date and time.
    """

    try:
        return Updated_Time(value).timestamp
    except ValueError as error:
        raise argparse.ArgumentTypeError("Not a valid date: " + error.message)

def parse_args():
    """
    Parse command line arguments.
    """

    config = configparser.RawConfigParser()
    config.read("settings.cfg")

    description = "Obtain JIRA issue data and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="JIRA project key")
    parser.add_argument("--username", default=config.get("jira", "username"),
                        help="JIRA username")
    parser.add_argument("--password", default=config.get("jira", "password"),
                        help="JIRA password")
    parser.add_argument("--server", default=config.get("jira", "server"),
                        help="JIRA server URL")
    parser.add_argument("--updated-since", default=None, dest="updated_since",
                        type=validate_date,
                        help="Only fetch issues changed since the timestamp (YYYY-MM-DD HH:MM)")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    tracker = Update_Tracker(project, args.updated_since)
    updated_since = tracker.get_updated_since()

    options = {
        "server": args.server
    }
    jira = Jira(project, updated_since)
    latest_update = jira.process(args.username, args.password, options)

    tracker.save_updated_since(latest_update)

if __name__ == "__main__":
    main()
