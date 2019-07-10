"""
Script to retrieve or generate project-specific salts.
"""

from argparse import ArgumentParser, Namespace
import logging
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.salt import Salt

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Retrieve the project salts')
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

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    with Salt(project, user=args.user, password=args.password,
              host=args.host, database=args.database) as store:
        salt, pepper = store.execute()

        logging.info('Salt: %s', salt)
        logging.info('Pepper: %s', pepper)

if __name__ == '__main__':
    main()
