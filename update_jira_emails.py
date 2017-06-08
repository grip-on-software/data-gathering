"""
Script to update old dropin files with fresh developer data, including emails.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import json
import logging
import os.path
from gatherer.config import Configuration
from gatherer.jira import Jira, Update_Tracker
from gatherer.jira.query import Query
from gatherer.log import Log_Setup
from gatherer.domain import Project

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = "Update email addresses in dropin developer data from JIRA"
    parser = argparse.ArgumentParser(description=description)
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

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    data_path = os.path.join(project.dropins_key, 'data_developer.json')
    with open(data_path) as data_file:
        developers = json.load(data_file)

    options = {
        "server": args.server
    }
    jira = Jira(project, Update_Tracker.NULL_TIMESTAMP)
    query = Query(jira, args.username, args.password, options)
    parser = jira.get_type_cast("developer")
    api = query.api

    for developer in developers:
        users = api.search_users(developer['name'], includeInactive=True)
        if not users:
            raise ValueError('Developer {} not found on JIRA'.format(developer['name']))

        parser.parse(users[0])

    jira.get_table("developer").write(project.dropins_key)
    logging.info('Written new developer table to %s', data_path)

if __name__ == '__main__':
    main()
