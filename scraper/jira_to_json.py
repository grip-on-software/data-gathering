"""
Script to retrieve JIRA issue data and convert it to JSON format readable by
the database importer.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from gatherer.config import Configuration
from gatherer.jira import Jira, Updated_Time, Update_Tracker
from gatherer.log import Log_Setup
from gatherer.domain import Project, source

def validate_date(value: str) -> str:
    """
    Check whether a given value can be correctly parsed as a timestamp with
    a date and time.
    """

    try:
        return Updated_Time(value).timestamp
    except ValueError as error:
        raise ArgumentTypeError(f"Not a valid date: {error}") from error

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = "Obtain JIRA issue data and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="JIRA project key")
    parser.add_argument("--username", default=config.get("jira", "username"),
                        help="JIRA username")
    parser.add_argument("--password", default=config.get("jira", "password"),
                        help="JIRA password")
    parser.add_argument("--server", default=config.get("jira", "server"),
                        help="JIRA server URL")
    parser.add_argument("--query", default=None, help="Additional query")
    parser.add_argument("--updated-since", default=None, dest="updated_since",
                        type=validate_date,
                        help="Only fetch issues changed since the timestamp (YYYY-MM-DD HH:MM)")
    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    tracker = Update_Tracker(project, args.updated_since)
    updated_since = tracker.get_updated_since()

    jira = Jira(project, updated_since)
    jira_source = source.Jira('jira', url=args.server, name=args.project,
                              username=args.username, password=args.password)
    latest_update = jira.process(jira_source, query=args.query)

    tracker.save_updated_since(latest_update)

if __name__ == "__main__":
    main()
