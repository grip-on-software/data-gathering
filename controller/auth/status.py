"""
API to track dashboard status (on POST) or provide controller status (on GET).

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University

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

import cgi
import cgitb
import ipaddress
import json
import os
from pathlib import Path
from typing import Dict, Optional, Union
from http.server import BaseHTTPRequestHandler
import psutil
import etcd3
import Pyro4

from gatherer.config import Configuration

StatusField = Dict[str, Union[bool, str]]

class Status:
    """
    A status provider.
    """

    @property
    def key(self) -> str:
        """
        Retrieve the status provider name which can be used in a dictionary of
        collected status information.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def generate(self) -> StatusField:
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

    def __init__(self, project_key: str) -> None:
        super().__init__()
        self._project_key = project_key

    @property
    def key(self) -> str:
        return 'database'

    def generate(self) -> StatusField:
        try:
            gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
            return gatherer.get_database_status(self._project_key)
        except Pyro4.errors.NamingError as error:
            return {
                'ok': False,
                'message': str(error)
            }

class Tracker_Status(Status):
    """
    Status provider for the update tracker schedule.
    """

    def __init__(self, project_key: str) -> None:
        super().__init__()
        self._project_key = project_key

    @property
    def key(self) -> str:
        return 'tracker'

    def generate(self) -> StatusField:
        try:
            gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
            return gatherer.get_tracker_status(self._project_key)
        except Pyro4.errors.NamingError as error:
            return {
                'ok': False,
                'message': str(error)
            }

class Permissions_Status(Status):
    """
    Status provider for the controller/agent file permissions.
    """

    def __init__(self, project_key: str, agent_key: str) -> None:
        super().__init__()
        self._project_key = project_key
        self._agent_key = agent_key

    @property
    def key(self) -> str:
        return 'permissions'

    def generate(self) -> StatusField:
        try:
            controller = Pyro4.Proxy("PYRONAME:gros.controller")
            return controller.get_permissions_status(self._project_key,
                                                     self._agent_key)
        except Pyro4.errors.NamingError as error:
            return {
                'ok': False,
                'message': str(error)
            }

class Lock_Status(Status):
    """
    Status provider for the agent lock.
    """

    def __init__(self, project_key: str) -> None:
        super().__init__()
        self._project_key = project_key

    @property
    def key(self) -> str:
        return 'lock'

    def generate(self) -> StatusField:
        try:
            client = etcd3.client(timeout=2)
            lock = client.lock(f'/agent/{self._project_key}')
            if lock.is_acquired():
                return {
                    'ok': False,
                    'message': 'Another process has acquired the agent lock'
                }
        except etcd3.exceptions.Etcd3Exception as error:
            return {
                'ok': False,
                'message': repr(error)
            }

        return {
            'ok': True
        }

class Importer_Status(Status):
    """
    Status provider for the export processes.
    """

    @property
    def key(self) -> str:
        return 'importer'

    def generate(self) -> StatusField:
        for proc in psutil.process_iter(attrs=['name', 'username']):
            if proc.info['username'] == 'exporter' and 'jenkins.sh' in proc.info['name']:
                return {
                    'ok': False,
                    'message': 'An import process is currently running'
                }

        return {'ok': True}


class Daemon_Status(Status):
    """
    Status provider for the internal daemons.
    """

    REQUIRED = set(['gros.gatherer', 'gros.controller', 'gros.exporter'])

    @property
    def key(self) -> str:
        return 'daemon'

    def generate(self) -> StatusField:
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
                'message': f'Missing daemons: {", ".join(missing)}'
            }

        return {
            'ok': True,
            'message': 'All daemons are located'
        }

class Network_Status(Status):
    """
    Status provider that checks if the remote address is within an acceptable
    list of addresses for the project.
    """

    def __init__(self, project_key: str, address: str) -> None:
        super().__init__()
        self._project_key = project_key
        self._address = address

    @property
    def key(self) -> str:
        return 'network'

    def generate(self) -> StatusField:
        config = Configuration.get_settings()
        if not config.has_option('network', self._project_key):
            return {
                'ok': True,
                'message': 'No network defined for project'
            }

        try:
            address = ipaddress.ip_address(self._address)
        except ValueError as error:
            return {
                'ok': False,
                'message': f'Remote address is malformed: {error}'
            }

        try:
            nets = config.get('network', self._project_key).split(',')
            networks = set(ipaddress.ip_network(net.strip()) for net in nets)
        except ValueError as error:
            return {
                'ok': False,
                'message': f'Project has malformed networks defined: {error}'
            }

        if not any(address in network for network in networks):
            return {
                'ok': False,
                'message': f'Remote address {self._address} is not in defined networks'
            }

        return {
            'ok': True
        }

class Configuration_Status(Status):
    """
    Status provider that checks if local agent configuration is sane and
    provides the configuration to the client.
    """

    def __init__(self, status: Dict[str, StatusField]) -> None:
        super().__init__()
        self._status = status

    @property
    def key(self) -> str:
        return 'configuration'

    def generate(self) -> StatusField:
        env_path = Path(os.getenv('CONTROLLER_ENV_FILE', 'env'))
        if not env_path.exists():
            return {
                'ok': False,
                'message': 'Agent environment configuration is missing'
            }

        if any(not part.get('ok') for part in self._status.values()):
            return {
                'ok': False,
                'message': 'Cannot look up environment due to other problems'
            }

        with env_path.open('r', encoding='utf-8') as env_file:
            return {
                'ok': True,
                'contents': env_file.read()
            }

class Total_Status(Status):
    """
    Status provider that accumulates the other status information.
    """

    def __init__(self, status: Dict[str, StatusField]) -> None:
        super().__init__()
        self._status = status

    @property
    def key(self) -> str:
        return 'total'

    def generate(self) -> StatusField:
        try:
            is_ok = all(part['ok'] for part in self._status.values())
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

    _responses = dict(BaseHTTPRequestHandler.responses).copy()

    def __init__(self, code: int = 400, message: Optional[str] = None) -> None:
        super().__init__(message, code)
        self._message = message
        self._code = code

    @property
    def code(self) -> int:
        """
        Retrieve the numeric status code.
        """

        return self._code

    @property
    def status(self) -> str:
        """
        Retrieve the HTTP status line.
        """

        if self._code in self._responses:
            return self._responses[self._code][0]

        return f'{self._code} Custom Error'

    @property
    def message(self) -> str:
        """
        Retrieve the human-readable message explaining the error.
        """

        if self._message is not None:
            return self._message

        if self._code in self._responses:
            return self._responses[self._code][1]

        return f'Controller error: {self._code}'

def setup_log() -> None:
    """
    Set up logging.
    """

    cgitb.enable()

def receive_status(fields: cgi.FieldStorage, project_key: str) -> None:
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
    except ValueError as error:
        raise RuntimeError('Status field must be valid JSON') from error

    gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
    if not gatherer.add_bigboat_status(project_key, statuses, source):
        # If there are any database problems, write the statuses to
        # a controller file for later import.
        controller = Pyro4.Proxy("PYRONAME:gros.controller")
        controller.create_controller(project_key)
        controller.update_status_file(project_key, 'data_status.json', statuses)

    print('Status: 202 Accepted')
    print()

def display_status(project_key, agent_key):
    """
    Display server status to the agent as JSON.
    """

    status = {}
    generators = [
        Database_Status(project_key),
        Tracker_Status(project_key),
        Permissions_Status(project_key, agent_key),
        Lock_Status(project_key),
        Importer_Status(),
        Daemon_Status(),
        Network_Status(project_key, os.getenv('REMOTE_ADDR', '')),
        Configuration_Status(status),
        Total_Status(status),
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

def get_project_key(fields: cgi.FieldStorage, key: str = "project",
                    default: Optional[str] = None) -> str:
    """
    Retrieve and validate the project key from a CGI request.
    """

    if key not in fields:
        if default is None:
            raise RuntimeError('Project must be specified')

        return default

    projects = fields.getlist(key)
    if len(projects) != 1:
        raise RuntimeError('Exactly one project must be specified')

    project_key = projects[0]
    if not project_key.isupper() or not project_key.isalpha():
        raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

    return project_key

def main() -> None:
    """
    Main entry point.
    """

    setup_log()
    fields = cgi.FieldStorage()
    try:
        method = os.getenv('REQUEST_METHOD')

        project_key = get_project_key(fields)

        if method == 'POST':
            receive_status(fields, project_key)
        elif method == 'GET':
            agent_key = get_project_key(fields, 'agent', project_key)
            display_status(project_key, agent_key)
        else:
            raise StatusError(501)
    except StatusError as error:
        print(f'Status: {error.status}')
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
