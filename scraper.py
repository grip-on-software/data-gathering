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

    @staticmethod
    def _is_running():
        try:
            subprocess.check_call([
                'pgrep', '-f', '/home/agent/docker-scraper.sh',
            ], stdout=None, stderr=None)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

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

        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(400, 'Must be POSTed')

        if self._is_running():
            raise cherrypy.HTTPError(503, 'Another scrape process is already running')

        # Skip the controller status check at preflight: We want to run the
        # scrape now as a test run, and not bother with schedules.
        environment = os.environ.copy()
        environment['PREFLIGHT_ARGS'] = '--skip'
        process = subprocess.Popen(['/bin/bash', '/etc/periodic/daily/scrape'],
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
                        help='Bind address (default: 0.0.0.0, 127.0.0.1 in debug')
    parser.add_argument('--port', default=7070, type=int,
                        help='Port to listen to (default: 7070')
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()
    if args.listen is not None:
        bind_address = args.listen
    elif args.debug:
        bind_address = '127.0.0.1'
    else:
        bind_address = '0.0.0.0'

    config = {
        'global': {
            'server.socket_host': bind_address,
            'server.socket_port': args.port,
            'request.show_tracebacks': args.debug
        },
        '/': {
            'error_page.default': Scraper.json_error,
        }
    }
    cherrypy.quickstart(Scraper(), config=config)

if __name__ == '__main__':
    main()