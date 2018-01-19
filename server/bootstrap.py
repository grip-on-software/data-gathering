"""
Generic Web service bootstrapper.
"""

import argparse
import logging.config
import os
import cherrypy
import cherrypy.daemon
from gatherer.config import Configuration
from gatherer.log import Log_Setup
from .authentication import Authentication

class Bootstrap(object):
    """
    Server setup procedure.
    """

    def __init__(self):
        self.config = Configuration.get_settings()
        self.args = None

    @property
    def description(self):
        """
        Retrieve a descriptive message of the server to be used in command-line
        help text.
        """

        raise NotImplementedError('Must be overridden by subclasses')

    def _parse_args(self):
        """
        Parse command line arguments.
        """

        # Default authentication scheme
        auth = self.config.get('deploy', 'auth')
        if not Configuration.has_value(auth):
            auth = 'ldap'

        parser = argparse.ArgumentParser(description=self.description)
        Log_Setup.add_argument(parser, default='INFO')
        parser.add_argument('--debug', action='store_true', default=False,
                            help='Display logging in terminal and traces on web')
        parser.add_argument('--log-path', dest='log_path', default='.',
                            help='Path to store logs at in production')
        parser.add_argument('--auth', choices=Authentication.get_types(),
                            default=auth, help='Authentication scheme')
        parser.add_argument('--port', type=int, default=8080,
                            help='Port for the server to listen on')
        parser.add_argument('--daemonize', action='store_true', default=False,
                            help='Run the server as a daemon')
        parser.add_argument('--pidfile', help='Store process ID in file')

        server = parser.add_mutually_exclusive_group()
        server.add_argument('--fastcgi', action='store_true', default=False,
                            help='Start a FastCGI server instead of HTTP')
        server.add_argument('--scgi', action='store_true', default=False,
                            help='Start a SCGI server instead of HTTP')
        server.add_argument('--cgi', action='store_true', default=False,
                            help='Start a CGI server instead of the HTTP')

        self.add_args(parser)
        return parser.parse_args()

    def add_args(self, parser):
        """
        Register additional arguments to the argument parser.
        """

        raise NotImplementedError('Must be overridden by subclasses')

    def _build_log_file_handler(self, filename):
        return {
            'level': self.args.log,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(self.args.log_path, filename),
            'formatter': 'void',
            'maxBytes': 10485760,
            'backupCount': 20,
            'encoding': 'utf8'
        }

    def _setup_log(self):
        """
        Setup logging.
        """

        stream_handler = {
            'level': self.args.log,
            'class':'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        }

        config = {
            'version': 1,
            'formatters': {
                'void': {
                    'format': ''
                },
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'handlers': {
                'default': stream_handler.copy(),
                'cherrypy_console': stream_handler.copy(),
                'cherrypy_access': self._build_log_file_handler('access.log'),
                'cherrypy_error': self._build_log_file_handler('error.log'),
                'python': self._build_log_file_handler('python.log')
            },
            'loggers': {
                '': {
                    'handlers': ['default' if self.args.debug else 'python'],
                    'level': self.args.log
                },
                'cherrypy.access': {
                    'handlers': ['cherrypy_console' if self.args.debug else 'cherrypy_access'],
                    'level': self.args.log,
                    'propagate': False
                },
                'cherrypy.error': {
                    'handlers': ['cherrypy_console' if self.args.debug else 'cherrypy_error'],
                    'level': self.args.log,
                    'propagate': False
                },
            }
        }
        logging.config.dictConfig(config)

    def mount(self, conf):
        """
        Mount the application on the server. `conf` is a dictionary of cherrypy
        configuration sections with which the application can be configured.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def bootstrap(self):
        """
        Start the WSGI server.
        """

        # Setup arguments and configuration
        self.args = self._parse_args()
        self._setup_log()
        conf = {
            'global': {
                'request.show_tracebacks': self.args.debug
            },
            '/': {
                'tools.sessions.on': True
            }
        }
        cherrypy.config.update({'server.socket_port': self.args.port})

        # Start the application and server daemon.
        self.mount(conf)
        cherrypy.daemon.start(daemonize=self.args.daemonize,
                              pidfile=self.args.pidfile,
                              fastcgi=self.args.fastcgi,
                              scgi=self.args.scgi,
                              cgi=self.args.cgi)
