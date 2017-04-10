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
import os
import subprocess
import sys
import tempfile
import urllib.parse

class Permissions(object):
    """
    Object that updated access and permissions for a project's agent.
    """

    CREATE_PERMISSIONS = '2770'

    def __init__(self, project_key):
        self._home_directory = os.path.join('/agents', project_key)
        self._username = 'agent-{}'.format(project_key)
        self._ssh_directory = os.path.join('/etc/ssh/control/', self._username)

    def _create_directory(self, directory):
        subprocess.check_call([
            'sudo', 'mkdir', '-m', self.CREATE_PERMISSIONS, directory
        ])
        self._update_owner(directory)

    def _update_owner(self, directory):
        subprocess.check_call([
            'sudo', 'chown', '-R',
            '{}:controller'.format(self._username), directory
        ])

    def update_user(self):
        """Update agent home directory."""
        if os.path.exists(self._home_directory):
            subprocess.check_call(['sudo', 'rm', '-rf', self._home_directory])
        else:
            subprocess.check_call([
                'sudo', 'adduser',
                '-M', # Do not create home directory at this point
                '-N', # Do not create any additional groups
                '-d', self._home_directory,
                '-l', '/usr/local/bin/upload.sh',
                '-g', 'agents',
                self._username
            ])

        self._create_directory(self._home_directory)

    def update_public_key(self, public_key):
        """Update authorized public key."""

        if os.path.exists(self._ssh_directory):
            subprocess.check_call(['sudo', 'rm', '-rf', self._ssh_directory])

        self._create_directory(self._ssh_directory)

        key_filename = os.path.join(self._ssh_directory, 'authorized_keys')
        with open(key_filename, 'w') as key_file:
            key_file.write(public_key)

    def update_permissions(self):
        """
        Change permissions such that only the agent can access the directories.
        """

        for directory in (self._home_directory, self._ssh_directory):
            self._update_owner(directory)
            subprocess.check_call(['sudo', 'chmod', '2700', directory])

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
