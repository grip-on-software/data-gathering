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
import urllib.parse
import Pyro4

class Permissions(object):
    """
    Object that updates access and permissions for a project's agent.
    """

    def __init__(self, project_key):
        self._controller = Pyro4.Proxy("PYRONAME:gros.controller")
        self._project_key = project_key

    def update_user(self):
        """Update agent home directory."""

        self._controller.create_agent(self._project_key)

    def update_public_key(self, public_key):
        """Update authorized public key."""

        self._controller.update_public_key(self._project_key, public_key)

    def update_permissions(self):
        """
        Change permissions such that only the agent can access the directories.
        """

        self._controller.update_permissions(self._project_key)

def setup_log():
    """
    Set up logging.
    """

    cgitb.enable()

def get_project_key():
    """Retrieve and validate the project key from a CGI request."""
    form = cgi.FieldStorage()
    if "project" not in form:
        raise RuntimeError('Project must be specified')

    project_key = form["project"].value
    if not project_key.isupper() or not project_key.isalpha():
        raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

    return project_key

def get_public_key():
    """Retrieve the public key that must be POSTed in the request."""

    post_query = sys.stdin.read()
    post_data = urllib.parse.parse_qs(post_query)
    if "public_key" not in post_data:
        raise RuntimeError('Public key must be provided as a POST message')
    if len(post_data["public_key"]) != 1:
        raise RuntimeError('Exactly one public key must be provided in POST')

    return post_data["public_key"][0]

def get_temp_filename():
    """
    Retrieve a secure (not guessable) temporary file name.
    """

    with tempfile.NamedTemporaryFile() as tmpfile:
        filename = tmpfile.name

    return filename

def main():
    """
    Main entry point.
    """

    setup_log()
    try:
        project_key = get_project_key()
        public_key = get_public_key()
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    permissions = Permissions(project_key)
    permissions.update_user()

    permissions.update_public_key(public_key)

    permissions.update_permissions()

    print('Content-Type: text/json')
    print()
    json.dump(sys.stdout, {})

if __name__ == "__main__":
    main()
