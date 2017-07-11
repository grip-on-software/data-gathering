"""
Module for initializing logging.
"""

from builtins import object
import logging
from logging.handlers import HTTPHandler
import os
import ssl
from .config import Configuration

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
        parser.add_argument('--log', default='WARNING', choices=options,
                            help='log level (WARNING by default)')

    @staticmethod
    def add_upload_arguments(parser):
        """
        Add additional arguments to configure the transfer of logging data to
        a controller API server. This only applies if the script is running
        on an agent with an environment that contains the AGENT_LOGGING variable
        globally.
        """

        if os.getenv('AGENT_LOGGING') is None:
            return

        config = Configuration.get_settings()
        host = config.get('ssh', 'host')
        cert = config.get('ssh', 'cert')

        parser.add_argument('--ssh', default=host,
                            help='Controller API host to upload logs to')
        parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                            help='Do not upload logs to controller API host')
        parser.add_argument('--cert', default=cert,
                            help='HTTPS certificate of controller API host')

    @classmethod
    def parse_args(cls, args):
        """
        Retrieve the log level from parsed arguments and configure log packet
        uploading if possible.
        """

        cls.init_logging(args.log)
        agent_log = os.getenv('AGENT_LOGGING')
        if agent_log is not None and hasattr(args, 'project') and hasattr(args, 'ssh') and args.ssh:
            cls.add_agent_handler(args.ssh, args.cert, args.project)

    @staticmethod
    def init_logging(log_level):
        """
        Initialize logging for the scraper process.
        """

        logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                            level=getattr(logging, log_level.upper(), None))

    @staticmethod
    def add_agent_handler(host, cert_file, project_key):
        """
        Create a HTTPS-based logging handler that sends logging messages to
        the controller server.
        """

        # Workaround: HTTPHandler sets Host header twice (once via constructor
        # or HTTP(S)Connection and once manually), which causes lighttpd
        # servers to reject the request (as per RFC7320 sec. 5.4 p. 44).
        # When the host can be extracted from the GET URL, however, all
        # subsequent Host headers are ignored (as per RFC2616 sec. 5.2 p. 37).
        url = "https://{}/auth/log.py?project={}".format(host, project_key)
        context = ssl.create_default_context(cafile=cert_file)
        try:
            # Python 2 logging handler does not support HTTPS connecions.
            # pylint: disable=unexpected-keyword-arg
            handler = HTTPHandler(host, url, method='POST', secure=True,
                                  context=context)
        except TypeError:
            logging.exception('Cannot initialize agent logging handler, incompatible HTTPHandler')
            return

        # Add the handler to the root logger.
        handler.setLevel(logging.WARNING)
        logging.getLogger().addHandler(handler)
