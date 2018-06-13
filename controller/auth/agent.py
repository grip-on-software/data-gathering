"""
Authentication API for external agents.
"""

from __future__ import print_function
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import object
import cgi
import cgitb
import json
import sys
import tempfile
try:
    import urllib.parse
except ImportError:
    raise
import Pyro4

class Permissions(object):
    """
    Object that updates access and permissions for a project's agent.
    """

    def __init__(self, project_key):
        self._controller = Pyro4.Proxy("PYRONAME:gros.controller")
        self._project_key = project_key

    def get_home_directory(self):
        """
        Retrieve the home directory of the agent user.
        """

        return self._controller.get_home_directory(self._project_key)

    def update_user(self, full=True):
        """Update agent home directory."""

        if full:
            self._controller.create_agent(self._project_key)
        else:
            self._controller.clean_home_subdirectories(self._project_key,
                                                       ('update',))

    def update_public_key(self, public_key):
        """
        Update authorized public key.

        Returns whether the public key already exists with the same contents.
        """

        return self._controller.update_public_key(self._project_key, public_key)

    def update_permissions(self):
        """
        Change permissions such that only the agent can access the directories.
        """

        self._controller.update_permissions(self._project_key)

class Response(object):
    """
    Object that formulates the response and writes additional files.
    """

    def __init__(self, project_key):
        self._gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
        self._project_key = project_key

    def get_update_trackers(self, home_directory):
        """
        Retrieve update tracking files and store them in the agent's update
        directory.
        """

        self._gatherer.get_update_trackers(self._project_key, home_directory)

    def get_salts(self):
        """
        Retrieve project-specific encryption salts.
        """

        return self._gatherer.get_salts(self._project_key)

    def get_usernames(self):
        """
        Retrieve username patterns that need to be replaced before encryption.
        """

        return self._gatherer.get_usernames(self._project_key)

class Parameters(object):
    """
    Object that holds GET and POST data from a CGI request.
    """

    def __init__(self):
        post_query = sys.stdin.read()
        self._post_data = urllib.parse.parse_qs(post_query)
        self._get_data = cgi.FieldStorage()

    def get_project_key(self):
        """Retrieve and validate the project key from a CGI request."""

        if "project" not in self._get_data:
            raise RuntimeError('Project must be specified')

        projects = self._get_data.getlist("project")
        if len(projects) != 1:
            raise RuntimeError('Exactly one project must be specified in GET')

        project_key = projects[0]
        if not project_key.isupper() or not project_key.isalpha():
            raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

        return project_key

    def get_public_key(self):
        """Retrieve the public key that must be POSTed in the request."""

        if "public_key" not in self._post_data:
            raise RuntimeError('Public key must be provided as a POST message')
        if len(self._post_data["public_key"]) != 1:
            raise RuntimeError('Exactly one public key must be provided in POST')

        return self._post_data["public_key"][0]

def get_temp_filename():
    """
    Retrieve a secure (not guessable) temporary file name.
    """

    with tempfile.NamedTemporaryFile() as tmpfile:
        filename = tmpfile.name

    return filename

def setup_log():
    """
    Set up logging.
    """

    cgitb.enable()

def main():
    """
    Main entry point.
    """

    setup_log()
    try:
        params = Parameters()
        project_key = params.get_project_key()
        public_key = params.get_public_key()
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    permissions = Permissions(project_key)

    same_key = permissions.update_public_key(public_key):
    # If the public key is the same, then we do not need to replace the
    # entire user home directory.
    permissions.update_user(full=not same_key)

    response = Response(project_key)
    response.get_update_trackers(permissions.get_home_directory())
    salt, pepper = response.get_salts()
    usernames = response.get_usernames()

    permissions.update_permissions()

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
