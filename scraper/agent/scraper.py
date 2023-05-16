"""
Listener server which starts a Docker-based scrape job when a request is made
to the server.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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
import os
from pathlib import Path
import subprocess
import time
from typing import Dict, Optional, Union
import cherrypy
import gatherer

Status = Dict[str, Union[bool, str]]

class Scraper:
    # pylint: disable=no-self-use
    """
    Scraper listener.
    """

    HOME_DIRECTORY = '/home/agent'

    def __init__(self, domain: Optional[str] = None) -> None:
        self._domain = domain

    @classmethod
    def _is_running(cls) -> bool:
        try:
            subprocess.check_call([
                'pgrep', '-f', f'{cls.HOME_DIRECTORY}/scraper/agent/run.sh',
            ], stdout=None, stderr=None)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def _check_host(self) -> None:
        if self._domain is not None:
            host = cherrypy.request.headers.get('Host', '')
            if host != self._domain:
                raise cherrypy.HTTPError(403, 'Invalid Host header')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self) -> Status:
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
    def scrape(self) -> Status:
        """
        Handle scrape request.
        """

        self._check_host()

        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(400, 'Must be POSTed')

        if self._is_running():
            raise cherrypy.HTTPError(503, 'Another scrape process is already running')

        path = Path(f'{self.HOME_DIRECTORY}/scraper/agent/scrape.sh')
        if not path.exists():
            raise cherrypy.HTTPError(500, f'Cannot find scraper at {path}')

        # Skip the controller status check at preflight: We want to run the
        # scrape now as a test run, and not bother with schedules.
        environment = os.environ.copy()
        environment['PREFLIGHT_ARGS'] = '--skip'

        with subprocess.Popen(['/bin/bash', path], stdout=None, stderr=None,
                              env=environment) as process:
            # Poll once after freeing CPU to check if the process has started.
            time.sleep(0.1)
            process.poll()
            if process.returncode is not None and process.returncode != 0:
                raise cherrypy.HTTPError(503, f'Status code {process.returncode}')

            cherrypy.response.status = 201
            return {'ok': True}

    @classmethod
    def json_error(cls, status: str, message: str, traceback: str, version: str) -> str:
        """
        Handle HTTP errors by formatting the exception details as JSON.
        """

        cherrypy.response.headers['Content-Type'] = 'application/json'
        try:
            with open(f'{cls.HOME_DIRECTORY}/VERSION', 'r',
                      encoding='utf-8') as version_file:
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

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    parser = ArgumentParser(description='Run scraper listener')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Output traces on web')
    parser.add_argument('--listen', default=None,
                        help='Bind address (default: localhost)')
    parser.add_argument('--port', default=7070, type=int,
                        help='Port to listen to (default: 7070)')
    parser.add_argument('--domain', default=None,
                        help='Host name and port to validate in headers')
    return parser.parse_args()

def main() -> None:
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
