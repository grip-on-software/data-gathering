"""
Internal daemon for handling agent user creation and update requests.
"""

import os.path
import subprocess
import Pyro4

@Pyro4.expose
class Controller(object):
    """
    Object that updates access and permissions for agents.
    """

    CREATE_PERMISSIONS = '2770'

    HOME_DIRECTORY = '/agents'
    USERNAME = 'agent-{}'
    SSH_DIRECTORY = '/etc/ssh/control'

    def _create_directory(self, project_key, directory):
        subprocess.check_call([
            'sudo', 'mkdir', '-m', self.CREATE_PERMISSIONS, directory
        ])
        self._update_owner(project_key, directory)

    def _update_owner(self, project_key, directory):
        subprocess.check_call([
            'sudo', 'chown', '-R',
            '{}:controller'.format(self.get_agent_user(project_key)), directory
        ])

    def get_home_directory(self, project_key):
        """
        Retrieve the home directory for a certain project.
        """

        return os.path.join(self.HOME_DIRECTORY, project_key)

    def get_home_subdirectories(self, project_key):
        """
        Retrieve the subdirectories of the home directory of a certain project
        which should be created in a clean version of the directory.

        Returns the full directory structure as a tuple of directories, ordered
        in the way they are created. This includes the home directory as the
        first element.
        """

        home_directory = self.get_home_directory(project_key)
        export_directory = os.path.join(home_directory, 'export')
        export_key_directory = os.path.join(export_directory, project_key)

        return (home_directory, export_directory, export_key_directory)

    def get_agent_user(self, project_key):
        """
        Retrieve the username of the agent for a certain project.
        """

        return self.USERNAME.format(project_key)

    def get_ssh_directory(self, project_key):
        """
        Retrieve the SSH directory for the agent's user of a certain project.
        """

        return os.path.join(self.SSH_DIRECTORY,
                            self.get_agent_user(project_key))

    def create_agent(self, project_key):
        """
        Create a user for the agent of the given project if it did not yet exist
        and return the username.

        Create the home directory of the user if it did not yet exist, alter
        the permissions and ownerships such that the controller can write to
        it temporarily, and return the path to the home directory.
        """

        home_directory = self.get_home_directory(project_key)
        username = self.get_agent_user(project_key)
        if os.path.exists(home_directory):
            subprocess.check_call(['sudo', 'rm', '-rf', home_directory])
        else:
            subprocess.check_call([
                'sudo', 'adduser',
                '-M', # Do not create home directory at this point
                '-N', # Do not create any additional groups
                '-d', home_directory,
                '-s', '/usr/local/bin/upload.sh',
                '-g', 'agents',
                username
            ])

        for directory in self.get_home_subdirectories(project_key):
            self._create_directory(project_key, directory)

        return home_directory

    def update_public_key(self, project_key, public_key):
        """Update authorized public key."""

        ssh_directory = self.get_ssh_directory(project_key)
        if os.path.exists(ssh_directory):
            subprocess.check_call(['sudo', 'rm', '-rf', ssh_directory])

        self._create_directory(project_key, ssh_directory)

        key_filename = os.path.join(ssh_directory, 'authorized_keys')
        with open(key_filename, 'w') as key_file:
            key_file.write(public_key)

    def update_permissions(self, project_key):
        """
        Change permissions such that only the agent can access the directories.
        """

        home_directories = self.get_home_subdirectories(project_key)
        ssh_directory = self.get_ssh_directory(project_key)
        for directory in reversed(home_directories + (ssh_directory,)):
            self._update_owner(project_key, directory)
            subprocess.check_call(['sudo', 'chmod', '2700', directory])

def main():
    """
    Main setup and event loop.
    """

    daemon = Pyro4.Daemon()
    object_name_server = Pyro4.locateNS()
    uri = daemon.register(Controller)
    object_name_server.register("gros.controller", uri)

    daemon.requestLoop()

if __name__ == "__main__":
    main()
