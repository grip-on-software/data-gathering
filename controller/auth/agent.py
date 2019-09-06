"""
Authentication API for external agents.
"""

import cgi
import cgitb
import json
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs
import etcd3
import Pyro4

class Permissions:
    """
    Object that updates access and permissions for a project's agent.
    """

    def __init__(self, project_key: str, agent_key: str) -> None:
        self._controller = Pyro4.Proxy("PYRONAME:gros.controller")
        self._project_key = project_key
        self._agent_key = agent_key

    def get_home_directory(self) -> str:
        """
        Retrieve the home directory of the agent user.
        """

        return self._controller.get_home_directory(self._agent_key)

    def update_user(self, full: bool = True) -> None:
        """
        Update agent home directory.

        If `full` is enabled (the default), then the home directory is removed
        and recreated. Otherwise, only the update tracker directory is removed
        and recreated. In either case, the update trackers must be retrieved
        and stored with correct permissions in the new directories after this.
        """

        if full:
            self._controller.create_agent(self._project_key, self._agent_key)
        else:
            self._controller.clean_home_subdirectories(self._project_key,
                                                       self._agent_key,
                                                       ('export', 'update',))

    def update_public_key(self, public_key: str) -> bool:
        """
        Update authorized public key.

        Returns whether the public key already exists for the agent with the
        exact same contents.
        """

        return self._controller.update_public_key(self._agent_key, public_key)

    def update_permissions(self) -> None:
        """
        Change permissions such that only the agent can access the directories.
        """

        self._controller.update_permissions(self._project_key, self._agent_key)

class Response:
    """
    Object that formulates the response and writes additional files.
    """

    def __init__(self, project_key: str) -> None:
        self._gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
        self._project_key = project_key

    def get_update_trackers(self, home_directory: str) -> None:
        """
        Retrieve update tracking files and store them in the agent's update
        directory.
        """

        self._gatherer.get_update_trackers(self._project_key, home_directory)

    def get_salts(self) -> Tuple[str, str]:
        """
        Retrieve project-specific encryption salts.
        """

        return self._gatherer.get_salts(self._project_key)

    def get_usernames(self) -> List[Dict[str, str]]:
        """
        Retrieve username patterns that need to be replaced before encryption.
        """

        return self._gatherer.get_usernames(self._project_key)

class Parameters:
    """
    Object that holds GET and POST data from a CGI request.
    """

    def __init__(self) -> None:
        post_query = sys.stdin.read()
        self._post_data = parse_qs(post_query)
        self._get_data = cgi.FieldStorage()

    def get_project_key(self, key: str = "project",
                        default: Optional[str] = None) -> str:
        """Retrieve and validate the project key from a CGI request."""

        if key not in self._get_data:
            if default is None:
                raise RuntimeError('Project must be specified')

            return default

        projects = self._get_data.getlist(key)
        if len(projects) != 1:
            raise RuntimeError('Exactly one project must be specified in GET')

        project_key = projects[0]
        if not project_key.isupper() or not project_key.isalpha():
            raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

        return project_key

    def get_public_key(self) -> str:
        """Retrieve the public key that must be POSTed in the request."""

        if "public_key" not in self._post_data:
            raise RuntimeError('Public key must be provided as a POST message')
        if len(self._post_data["public_key"]) != 1:
            raise RuntimeError('Exactly one public key must be provided in POST')

        return self._post_data["public_key"][0]

def setup_log() -> None:
    """
    Set up logging.
    """

    cgitb.enable()

def main() -> None:
    """
    Main entry point.
    """

    setup_log()
    try:
        params = Parameters()
        project_key = params.get_project_key()
        agent_key = params.get_project_key("agent", project_key)
        public_key = params.get_public_key()
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    try:
        client = etcd3.client(timeout=2)
        lock = client.lock('/agent/{}'.format(project_key), ttl=3600)
        if not lock.acquire(timeout=5):
            raise RuntimeError('Another process has acquired the lock')
    except (etcd3.exceptions.Etcd3Exception, RuntimeError) as error:
        print('Status: 503 Service Unavailable')
        print('Content-Type: text/plain')
        print()
        print('Could not lock the agent for updating: {!r}'.format(error))
        return

    try:
        permissions = Permissions(project_key, agent_key)

        same_key = permissions.update_public_key(public_key)
        # If the public key is the same, then we do not need to replace the
        # entire user home directory.
        permissions.update_user(full=not same_key)

        response = Response(project_key)
        response.get_update_trackers(permissions.get_home_directory())
        salt, pepper = response.get_salts()
        usernames = response.get_usernames()

        permissions.update_permissions()
    except (RuntimeError, OSError) as error:
        print('Status: 503 Service Unavailable')
        print('Content-Type: text/plain')
        print()
        print('Could not update the agent: {!r}'.format(error))
    finally:
        lock.release()

    print('Content-Type: application/json')
    print()
    json.dump({
        'salts': {
            'salt': salt,
            'pepper': pepper
        },
        'usernames': usernames
    }, sys.stdout)

if __name__ == "__main__":
    main()
