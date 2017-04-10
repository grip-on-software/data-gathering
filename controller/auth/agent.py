"""
Authentication API for external agents.
"""

from __future__ import print_function
from builtins import object
import cgi
import cgitb
import os
import shutil
import subprocess
import sys
import tempfile
import inform
try:
    from mock import MagicMock
    sys.modules['abraxas'] = MagicMock()
    from sshdeploy.key import Key
except ImportError:
    raise

class Permissions(object):
    """
    Object that updated access and permissions for a project's agent.
    """

    def __init__(self, project_key):
        self._home_directory = os.path.join('/agents', project_key)
        self._username = 'agent-{}'.format(project_key)
        self._ssh_directory = os.path.join('/etc/ssh/control/', self._username)

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
                '-g', 'agents',
                self._username
            ])

        os.mkdir(self._home_directory)
        # Force the mode change instead of masking out the umask on creation
        os.chmod(self._home_directory, 02770)

    def update_public_key(self, public_key_filename):
        """Update authorized public key."""

        if os.path.exists(self._ssh_directory):
            subprocess.check_call(['sudo', 'rm', '-rf', self._ssh_directory])

        os.mkdir(self._ssh_directory, 02700)

        shutil.move(public_key_filename,
                    os.path.join(self._ssh_directory, 'authorized_keys'))

    def update_permissions(self):
        """
        Change permissions such that the agent and controller can access.
        """

        for directory in (self._home_directory, self._ssh_directory):
            subprocess.check_call([
                'sudo', 'chown', '-R',
                '{}:controller'.format(self._username), directory
            ])

def setup_log():
    """
    Set up logging.
    """

    inform.Inform(mute=True)
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

def get_temp_filename():
    """
    Retrieve a secure (not guessable) temporary file name.
    """

    with tempfile.NamedTemporaryFile() as tmpfile:
        filename = tmpfile.name

    return filename

def generate_key_pair(project_key):
    """
    Generate a public and private key pair for the project.
    """

    data = {
        'purpose': 'agent for the {} project'.format(project_key),
        'keygen-options': '',
        'abraxas-account': False,
        'servers': {},
        'clients': {}
    }
    update = []
    key_file = get_temp_filename()
    key = Key(key_file, data, update, {}, False)
    key.generate()
    return key.keyname

def main():
    """
    Main entry point.
    """

    setup_log()
    try:
        project_key = get_project_key()
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print()
        print(str(error))

    permissions = Permissions(project_key)
    permissions.update_user()

    private_key_filename = generate_key_pair(project_key)
    permissions.update_public_key('{}.pub'.format(private_key_filename))

    permissions.update_permissions()

    # Output response
    with open(private_key_filename, 'r') as key_file:
        private_key = key_file.read()
    os.remove(private_key_filename)

    print('Content-Disposition: attachment; filename="id_rsa"')
    print()
    print(private_key)

if __name__ == "__main__":
    main()
