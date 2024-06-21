"""
Script to update old dropin files with fresh developer data, including emails.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from argparse import ArgumentParser, Namespace
import json
import logging
from gatherer.config import Configuration
from gatherer.jira import Jira, Update_Tracker
from gatherer.jira.query import Query
from gatherer.log import Log_Setup
from gatherer.domain import Project, source

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = "Update email addresses in dropin developer data from JIRA"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="JIRA project key")
    parser.add_argument("--username", default=config.get("jira", "username"),
                        help="JIRA username")
    parser.add_argument("--password", default=config.get("jira", "password"),
                        help="JIRA password")
    parser.add_argument("--server", default=config.get("jira", "server"),
                        help="JIRA server URL")

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

    data_path = project.dropins_key / 'data_developer.json'
    if not data_path.exists():
        raise OSError(f'Developer dropin file {data_path} does not exist')

    with data_path.open('r', encoding='utf-8') as data_file:
        developers = json.load(data_file)

    jira = Jira(project, Update_Tracker.NULL_TIMESTAMP)
    jira_source = source.Jira('jira', url=args.server, name=args.project,
                              username=args.username, password=args.password)
    query = Query(jira, jira_source)
    parser = jira.get_type_cast("developer")
    api = query.api

    for developer in developers:
        name = developer['name']
        users = api.search_users(name, includeInactive=True)
        if not users:
            raise ValueError(f"Developer {name} not found on JIRA")

        parser.parse(users[0])

    jira.get_table("developer").write(project.dropins_key)
    logging.info('Written new developer table to %s', data_path)

if __name__ == '__main__':
    main()
