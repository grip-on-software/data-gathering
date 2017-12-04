"""
Listener server which starts a Docker-based scrape job when a request is made
to the server.
"""

import json
import subprocess
import time
import cherrypy
import gatherer

class Scraper(object):
    # pylint: disable=no-self-use
    """
    Scraper listener.
    """

    @cherrypy.expose
    def scrape(self):
        """
        Handle scrape request.
        """

        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(400, 'Must be POSTed')

        try:
            subprocess.check_call([
                'pgrep', '-f', '/home/agent/docker-scraper.sh',
            ], stdout=None, stderr=None)
        except subprocess.CalledProcessError:
            pass
        else:
            raise cherrypy.HTTPError(503, 'Another scrape process is already running')

        process = subprocess.Popen(['/bin/bash', '/etc/periodic/daily/scrape'],
                                   stdout=None, stderr=None,
                                   env={'PREFLIGHT_ARGS': '--no-ssh'})

        # Poll once after freeing CPU to check if the process has started.
        time.sleep(0.1)
        process.poll()
        if process.returncode is not None and process.returncode != 0:
            raise cherrypy.HTTPError(503, 'Status code {}'.format(process.returncode))

        return json.dumps({'ok': True})

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

def main():
    """
    Main entry point.
    """

    config = {
        '/': {'error_page.default': Scraper.json_error}
    }
    cherrypy.quickstart(Scraper(), config=config)

if __name__ == '__main__':
    main()
