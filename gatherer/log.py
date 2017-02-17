"""
Module for initializing logging.
"""

import logging

class Log_Setup(object):
    """
    Utility class that initializes and registers logging options.
    """

    @staticmethod
    def add_argument(parser):
        """
        Register a log level argument in an argument parser.
        """

        options = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        parser.add_argument("--log", default='WARNING', choices=options,
                            help='log level (WARNING by default)')

    @staticmethod
    def parse_args(args):
        """
        Retrieve the log level from parsed arguments.
        """

        Log_Setup.init_logging(args.log)

    @staticmethod
    def init_logging(log_level):
        """
        Initialize logging for the scraper process.
        """

        logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                            level=getattr(logging, log_level.upper(), None))
