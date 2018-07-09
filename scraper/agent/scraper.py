"""
Listener server which starts a Docker-based scrape job when a request is made
to the server.
"""

import argparse
import json
import os
import subprocess
import time
import cherrypy
import gatherer

class Scraper(object):
    # pylint: disable=no-self-use
    """
    Scraper listener.
    """

    def __init__(self, domain=None):
        self._domain = domain

    @staticmethod
    def _is_running():
        try:
            subprocess.check_call([
                'pgrep', '-f', '/home/agent/scraper/agent/run.sh',
            ], stdout=None, stderr=None)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def _check_host(self):
        if self._domain is not None:
            host = cherrypy.request.headers.get('Host', '')
            if host != self._domain:
                raise cherrypy.HTTPError(403, 'Invalid Host header')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        """
        Check the status of the scrape process.
        """

        if self._is_running():
            return {
                'ok': True,
                'message': 'Scrape process is running'
            }

        cherrypy.response.status = 503
        return {
            'ok': False,
            'message': 'No scrape process is running'
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scrape(self):
        """
        Handle scrape request.
        """

        self._check_host()

        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(400, 'Must be POSTed')

        if self._is_running():
            raise cherrypy.HTTPError(503, 'Another scrape process is already running')

        path = '/home/agent/scraper/agent/scrape.sh'
        if not os.path.exists(path):
            raise cherrypy.HTTPError(500, 'Cannot find scraper {}'.format(path))

        # Skip the controller status check at preflight: We want to run the
        # scrape now as a test run, and not bother with schedules.
        environment = os.environ.copy()
        environment['PREFLIGHT_ARGS'] = '--skip'

        process = subprocess.Popen(['/bin/bash', path],
                                   stdout=None, stderr=None, env=environment)

        # Poll once after freeing CPU to check if the process has started.
        time.sleep(0.1)
        process.poll()
        if process.returncode is not None and process.returncode != 0:
            raise cherrypy.HTTPError(503, 'Status code {}'.format(process.returncode))

        cherrypy.response.status = 201
        return {'ok': True}

    @classmethod
    def json_error(cls, status, message, traceback, version):
        """
        Handle HTTP errors by formatting the exception details as JSON.
        """

        cherrypy.response.headers['Content-Type'] = 'application/json'
        try:
            with open('/home/agent/VERSION', 'r') as version_file:
                gatherer_version = version_file.readline().strip()
        except IOError:
            gatherer_version = gatherer.__version__
        return json.dumps({
            'ok': False,
            'error': {
                'status': status,
                'message': message,
                'traceback': traceback if cherrypy.request.show_tracebacks else None,
            },
            'version': {
                'gros-data-gathering-agent': gatherer_version,
                'cherrypy': version
            }
        })

def parse_args():
    """
    Parse command line arguments.
    """

    parser = argparse.ArgumentParser(description='Run scraper listener')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Output traces on web')
    parser.add_argument('--listen', default=None,
                        help='Bind address (default: localhost)')
    parser.add_argument('--port', default=7070, type=int,
                        help='Port to listen to (default: 7070')
    parser.add_argument('--domain', default=None,
                        help='Host name and port to validate in headers')
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()

    config = {
        'global': {
            'server.socket_port': args.port,
            'request.show_tracebacks': args.debug
        },
        '/': {
            'error_page.default': Scraper.json_error,
        }
    }
    if args.listen is not None:
        config['global']['server.socket_host'] = args.listen

    cherrypy.quickstart(Scraper(args.domain), config=config)

if __name__ == '__main__':
    main()
