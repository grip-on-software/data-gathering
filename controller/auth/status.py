"""
API to track dashboard status (on POST) or provide controller status (on GET).
"""

from __future__ import print_function
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import cgi
import cgitb
import json
import os
from http.server import BaseHTTPRequestHandler
import Pyro4

class Status(object):
    """
    A status provider.
    """

    @property
    def key(self):
        """
        Retrieve the status provider name which can be used in a dictionary of
        collected status information.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def generate(self):
        """
        Generate the status dictionary for this provider.

        The dictionary must contain the key 'ok' with a boolean value, and may
        contain 'message'.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class Database_Status(Status):
    """
    Status provider for the MonetDB database.
    """

    def __init__(self, project_key):
        super(Database_Status, self).__init__()
        self._project_key = project_key

    @property
    def key(self):
        return 'database'

    def generate(self):
        gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
        return gatherer.get_database_status(self._project_key)

class Tracker_Status(Status):
    """
    Status provider for the update tracker schedule.
    """

    def __init__(self, project_key):
        super(Tracker_Status, self).__init__()
        self._project_key = project_key

    @property
    def key(self):
        return 'tracker'

    def generate(self):
        gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
        return gatherer.get_tracker_status(self._project_key)

class Daemon_Status(Status):
    """
    Status provider for the internal daemons.
    """

    REQUIRED = set(['gros.gatherer', 'gros.controller', 'gros.exporter'])

    @property
    def key(self):
        return 'daemon'

    def generate(self):
        try:
            nameserver = Pyro4.locateNS()
        except Pyro4.errors.NamingError as error:
            return {
                'ok': False,
                'message': str(error)
            }

        current = set(nameserver.list().keys())
        missing = self.REQUIRED - current
        if missing:
            return {
                'ok': False,
                'message': 'Missing daemons: {}'.format(', '.join(missing))
            }

        return {
            'ok': True,
            'message': 'All daemons are located'
        }

class Total_Status(Status):
    """
    Status provider that accumulates the other status information.
    """

    def __init__(self, status):
        super(Total_Status, self).__init__()
        self._status = status

    @property
    def key(self):
        return 'total'

    def generate(self):
        try:
            is_ok = all([part['ok'] for part in self._status.values()])
            message = 'Everything OK' if is_ok else 'Some parts are not OK'
        except KeyError:
            is_ok = False
            message = 'Some parts have missing status'

        return {
            'ok': is_ok,
            'message': message
        }

class StatusError(RuntimeError):
    """
    Exception indicating an error handling the request, including a status code.
    """

    _responses = BaseHTTPRequestHandler.responses.copy()

    def __init__(self, code=400, message=None):
        super(StatusError, self).__init__(message, code)
        self._message = message
        self._code = code

    @property
    def code(self):
        """
        Retrieve the numeric status code.
        """

        return self._code

    @property
    def status(self):
        """
        Retrieve the HTTP status line.
        """

        if self._code in self._responses:
            return self._responses[self._code][0]

        return '{} Custom Error'.format(self._code)

    @property
    def message(self):
        """
        Retrieve the human-readable message explaining the error.
        """

        if self._message is not None:
            return self._message

        if self._code in self._responses:
            return self._responses[self._code][1]

        return 'Controller error: {}'.format(self._code)

def setup_log():
    """
    Set up logging.
    """

    cgitb.enable()

def receive_status(fields, project_key):
    """
    Receive and handle a status POST request from the agent.
    """

    if 'status' not in fields:
        raise RuntimeError('Status must be provided')

    status = fields.getlist('status')
    source = fields.getfirst('source')
    if len(status) != 1:
        raise RuntimeError('Exactly one status field must be specified')

    try:
        statuses = json.loads(status[0])
    except ValueError:
        raise RuntimeError('Status field must be valid JSON')

    gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
    if not gatherer.add_bigboat_status(project_key, statuses, source):
        # If there are any database problems, write the statuses to
        # a controller file for later import.
        controller = Pyro4.Proxy("PYRONAME:gros.controller")
        controller.create_controller(project_key)
        controller.update_status_file(project_key, 'data_status.json', statuses)

    print('Status: 202 Accepted')
    print()

def display_status(project_key):
    """
    Display server status to the agent as JSON.
    """

    status = {}
    generators = [
        Database_Status(project_key),
        Tracker_Status(project_key),
        Daemon_Status(),
        Total_Status(status)
    ]
    for generator in generators:
        status[generator.key] = generator.generate()

    if status['total']['ok']:
        print('Status: 200 OK')
    else:
        print('Status: 503 Service Unavailable')

    print('Content-type: application/json')
    print()
    print(json.dumps(status))

def main():
    """
    Main entry point.
    """

    setup_log()
    fields = cgi.FieldStorage()
    try:
        method = os.getenv('REQUEST_METHOD')

        if 'project' not in fields:
            raise RuntimeError('Project must be specified')

        projects = fields.getlist('project')
        if len(projects) != 1:
            raise RuntimeError('Exactly one project must be specified')

        project_key = projects[0]
        if not project_key.isupper() or not project_key.isalpha():
            raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

        if method == 'POST':
            receive_status(fields, project_key)
        elif method == 'GET':
            display_status(project_key)
        else:
            raise StatusError(501)
    except StatusError as error:
        print('Status: {}'.format(error.status))
        print('Content-Type: text/plain')
        print()
        print(error.message)
        return
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

if __name__ == '__main__':
    main()
