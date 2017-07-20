"""
Internal daemon for handling agent user creation and update requests.
"""

import json
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
    KEY_FILENAME = 'authorized_keys'
    CONTROLLER_DIRECTORY = '/controller'

    def _create_directory(self, project_key, directory, user=None,
                          permissions=None):
        if permissions is None:
            permissions = self.CREATE_PERMISSIONS

        subprocess.check_call([
            'sudo', 'mkdir', '-m', permissions, directory
        ])
        self._update_owner(project_key, directory, user=user)

    def _update_owner(self, project_key, path, user=None):
        if user is None:
            user = self.get_agent_user(project_key)

        subprocess.check_call([
            'sudo', 'chown', '-R', '{}:controller'.format(user), path
        ])

    def get_home_directory(self, project_key):
        """
        Retrieve the home directory for a certain project.
        """

        return os.path.join(self.HOME_DIRECTORY, project_key)

    def get_home_subdirectories(self, project_key, subpath=None):
        """
        Retrieve the subdirectories of the home directory of a certain project
        which should be created in a clean version of the directory.

        Returns the full directory structure as a tuple of directories, ordered
        in the way they are created. If `subpath` is `None`, then this includes
        the home directory as the first element, otherwise the subdirectory of
        the home directory is the first element. The following directories in
        the returned tuple are either subdirectories of this first element or
        any elements earlier in the tuple.
        """

        home_directory = self.get_home_directory(project_key)
        if subpath is not None:
            subpath_directory = os.path.join(home_directory, subpath)
            subpath_key_directory = os.path.join(subpath_directory, project_key)
            return (subpath_directory, subpath_key_directory)

        return (home_directory,) + \
                self.get_home_subdirectories(project_key, 'export') + \
                self.get_home_subdirectories(project_key, 'update')

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

    def get_controller_directory(self, project_key):
        """
        Retrieve the directory that the controller services use to work on the
        agent's data.
        """

        return os.path.join(self.CONTROLLER_DIRECTORY, project_key)

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

        key_filename = os.path.join(ssh_directory, self.KEY_FILENAME)
        with open(key_filename, 'w') as key_file:
            key_file.write(public_key)

    def update_permissions(self, project_key):
        """
        Change permissions such that only the agent can access the directories.
        """

        home_directories = self.get_home_subdirectories(project_key)
        ssh_directory = self.get_ssh_directory(project_key)
        for directory in reversed(home_directories):
            self._update_owner(project_key, directory)
            subprocess.check_call(['sudo', 'chmod', '2770', directory])

        key_filename = os.path.join(ssh_directory, self.KEY_FILENAME)
        subprocess.check_call(['sudo', 'chmod', '2600', key_filename])
        self._update_owner(project_key, ssh_directory)
        subprocess.check_call(['sudo', 'chmod', '2700', ssh_directory])

    def create_controller(self, project_key):
        """
        Create directories that the controller services use to work on the
        agent's data.
        """

        controller_path = self.get_controller_directory(project_key)
        if not os.path.exists(controller_path):
            self._create_directory(project_key, controller_path,
                                   user='exporter', permissions='0770')

    def update_status_file(self, project_key, filename, statuses):
        """
        Update a status logging file for the agent's health monitoring.
        """

        controller_path = self.get_controller_directory(project_key)
        data_filename = os.path.join(controller_path, filename)
        if not os.path.exists(data_filename):
            os.mknod(data_filename)
            subprocess.check_call(['sudo', 'chmod', '0660', data_filename])
            self._update_owner(project_key, data_filename, 'exporter')

        with open(data_filename, 'a') as data_file:
            json.dump(statuses, data_file, indent=None)
            data_file.write('\n')

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
