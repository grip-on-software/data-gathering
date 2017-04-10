"""
Script to retrieve update tracker files from the database for synchronization.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
from configparser import RawConfigParser
import datetime
import logging
import os
import pymonetdb
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = RawConfigParser()
    config.read("settings.cfg")

    parser = argparse.ArgumentParser(description='Retrieve the update trackers')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--user', default=config.get('database', 'username'),
                        help='username to connect to the database with')
    parser.add_argument('--password', default=config.get('database', 'password'),
                        help='password to connect to the database with')
    parser.add_argument('--host', default=config.get('database', 'host'),
                        help='host name of the database to connect to')
    parser.add_argument('--database', default=config.get('database', 'name'),
                        help='database name to retrieve from')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def update_file(project, filename, contents, update_date):
    """
    Check whether an update tracker file from a remote source is more up to date
    than our local version, and update it if so.
    """

    logging.debug('Filename: %s, remote updated: %s', filename, update_date)

    path = os.path.join(project.export_key, filename)
    update = True
    if os.path.exists(path):
        file_date = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        logging.debug('FS updated: %s', file_date)
        if file_date >= update_date:
            logging.info('Update tracker %s: Already up to date.', filename)
            update = False

    if update:
        logging.info('Updating file %s from remote tracker file', filename)
        with open(path, 'w') as tracker_file:
            tracker_file.write(contents)

        times = (datetime.datetime.now(), update_date)
        os.utime(path, tuple(int(time.strftime('%s')) for time in times))

def retrieve_database(project, user, password, host, database):
    """
    Retrieve the update tracker files from the database.
    """

    connection = pymonetdb.connect(username=user, password=password,
                                   hostname=host, database=database)

    cursor = connection.cursor()
    cursor.execute('SELECT project_id FROM gros.project WHERE name=%s LIMIT 1',
                   parameters=[project.key])
    row = cursor.fetchone()
    if not row:
        logging.warning("Project '%s' is not in the database", project.key)
        return

    project_id = row[0]

    cursor.execute('''SELECT filename, contents, update_date
                      FROM gros.update_tracker WHERE project_id=%s''',
                   parameters=[project_id])

    for row in cursor:
        filename, contents, update_date = row[0:3]
        update_file(project, filename, contents, update_date)

    connection.close()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    retrieve_database(project, args.user, args.password, args.host,
                      args.database)

if __name__ == '__main__':
    main()
