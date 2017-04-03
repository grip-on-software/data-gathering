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

def main():
    """
    Main entry point.
    """

    args = parse_args()
    connection = pymonetdb.connect(username=args.user, password=args.password,
                                   hostname=args.host, database=args.database)

    cursor = connection.cursor()
    cursor.execute('SELECT project_id FROM gros.project WHERE name=%s LIMIT 1',
                   parameters=[args.project])
    row = cursor.fetchone()
    if not row:
        logging.warning('Project %s is not in the database', args.project)
        return

    project_id = row[0]
    project = Project(args.project)

    cursor.execute('''SELECT filename, contents, update_date
                      FROM gros.update_tracker WHERE project_id=%s''',
                   parameters=[project_id])

    for row in cursor:
        filename, contents, update_date = row[0:3]
        logging.debug('DB filename: %s, updated: %s', filename, update_date)

        path = os.path.join(project.export_key, filename)
        update = True
        if os.path.exists(path):
            file_date = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            logging.debug('FS updated: %s', file_date)
            if file_date >= update_date:
                logging.info('Update tracker %s: Already up to date.', filename)
                update = False

        if update:
            logging.info('Updating file %s from database tracker', filename)
            with open(path, 'w') as update_file:
                update_file.write(contents)

            times = (datetime.datetime.now(), update_date)
            os.utime(path, tuple(int(time.strftime('%s')) for time in times))

    connection.close()

if __name__ == '__main__':
    main()
