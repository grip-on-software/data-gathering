"""
Internal daemon for handling agent user creation and update requests.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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

import json
import os
from pathlib import Path, PurePath
import subprocess
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union
import Pyro4

PathLike = Union[str, os.PathLike]

@Pyro4.expose
class Controller:
    """
    Object that updates access and permissions for agents.
    """

    # Permissions to use when creating a directory related to an agent.
    # The permissions ensure that the controller has access to it, and the
    # agent may not be able to log in while it has these permissions due to SSH
    # server security. Individual directories receive correct permissions after
    # all data is created.
    CREATE_PERMISSIONS = '2770'

    # Permissions to use when creating a file related to an agent.
    FILE_PERMISSIONS = '0660'

    # The root directory where agent home directories are created and kept.
    HOME_DIRECTORY = '/agents'
    # Format string for the user login name of an agent.
    USERNAME = 'agent-{}'
    # The directory where public keys of the agents are stored. This is kept
    # separate from the home directory for increased login security.
    SSH_DIRECTORY = '/etc/ssh/control'
    # The filename to use when storing the public keys in the key store.
    KEY_FILENAME = 'authorized_keys'
    # Directory where the controllers can work on copies of the agent data.
    CONTROLLER_DIRECTORY = '/controller'
    # Executable command to create a user. This command must accept options
    # to set up login shell, home directory path and other user properties and
    # create the user without any interactive prompts.
    ADD_USER_COMMAND = 'useradd'
    # File to create (owned by root:controller) without any contents in the
    # agent's home directory.
    HUSH_FILE = '.hushlogin'

    def _create_directory(self, agent_key: str, directory: PathLike,
                          user: Optional[str] = None,
                          permissions: Optional[str] = None) -> None:
        if permissions is None:
            permissions = self.CREATE_PERMISSIONS

        subprocess.check_call([
            'sudo', 'mkdir', '-m', permissions, str(directory)
        ])
        self._update_owner(agent_key, directory, user=user)

    def _create_file(self, agent_key: str, path: PathLike,
                     user: Optional[str] = None,
                     permissions: Optional[str] = None) -> None:
        if permissions is None:
            permissions = self.FILE_PERMISSIONS

        # Create empty file
        Path(path).touch()

        subprocess.check_call(['sudo', 'chmod', permissions, str(path)])
        self._update_owner(agent_key, path, user=user)

    def _update_owner(self, agent_key: str, path: PathLike,
                      user: Optional[str] = None) -> None:
        if user is None:
            user = self.get_agent_user(agent_key)

        subprocess.check_call([
            'sudo', 'chown', '-R', f'{user}:controller', str(path)
        ])

    def get_home_directory(self, agent_key: str) -> str:
        """
        Retrieve the home directory for a certain project's agent.
        """

        return str(PurePath(self.HOME_DIRECTORY, agent_key))

    def get_home_subdirectories(self, project_key: str, agent_key: str,
                                subpath: Optional[str] = None) -> Tuple[str, ...]:
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

        home_directory = self.get_home_directory(agent_key)
        if subpath is not None:
            subpath_directory = PurePath(home_directory, subpath)
            subpath_key_directory = PurePath(subpath_directory, project_key)
            return (str(subpath_directory), str(subpath_key_directory))

        return (home_directory,) + \
            self.get_home_subdirectories(project_key, agent_key, 'export') + \
            self.get_home_subdirectories(project_key, agent_key, 'update')

    def get_agent_user(self, project_key: str) -> str:
        """
        Retrieve the username of the agent for a certain project.
        """

        return self.USERNAME.format(project_key)

    def get_ssh_directory(self, project_key: str) -> str:
        """
        Retrieve the SSH directory for the agent's user of a certain project.
        """

        return str(PurePath(self.SSH_DIRECTORY,
                            self.get_agent_user(project_key)))

    def get_controller_directory(self, project_key: str) -> str:
        """
        Retrieve the directory that the controller services use to work on the
        agent's data.
        """

        return str(PurePath(self.CONTROLLER_DIRECTORY, project_key))

    def create_agent(self, project_key: str, agent_key: str) -> str:
        """
        Create a user for the agent of the given project if it did not yet exist
        and return the username.

        Create the home directory of the user if it did not yet exist, alter
        the permissions and ownerships such that the controller can write to
        it temporarily, and return the path to the home directory. The permisssions
        must be corrected using `update_permissions` afterward.
        """

        home_directory = Path(self.get_home_directory(agent_key))
        username = self.get_agent_user(agent_key)
        if home_directory.exists():
            subprocess.check_call(['sudo', 'rm', '-rf', home_directory])
        else:
            subprocess.check_call([
                'sudo', self.ADD_USER_COMMAND,
                '-M', # Do not create home directory at this point
                '-N', # Do not create any additional groups
                '-d', home_directory,
                '-s', '/usr/local/bin/upload.sh',
                '-g', 'agents',
                username
            ])

        for directory in self.get_home_subdirectories(project_key, agent_key):
            self._create_directory(agent_key, directory)

        path = Path(home_directory, self.HUSH_FILE)
        self._create_file(agent_key, path)

        return str(home_directory)

    def clean_home_subdirectories(self, project_key: str, agent_key: str,
                                  paths: Sequence[str]) -> None:
        """
        Clean certain subdirectories related to the user of the agent.
        """

        home_directory = self.get_home_directory(agent_key)
        subprocess.check_call(['sudo', 'chmod', '2770', home_directory])
        for path in paths:
            directory = PurePath(home_directory, path)
            subprocess.check_call(['sudo', 'rm', '-rf', directory])
            subdirectories = self.get_home_subdirectories(project_key,
                                                          agent_key, path)
            for subdirectory in subdirectories:
                self._create_directory(agent_key, subdirectory)

    def update_public_key(self, agent_key: str, public_key: str) -> bool:
        """
        Update authorized public key.

        Returns whether the public key already exists with the same contents.
        If this is not the case, then the authorized keys are replaced with the
        provided public key. In any case the permissions must be corrected using
        `update_permissions` afterward, otherwise the agent may not be able to
        log in on platforms with strict permissions checks for authorized keys.
        """

        ssh_directory = Path(self.get_ssh_directory(agent_key))
        key_filename = Path(ssh_directory, self.KEY_FILENAME)
        if ssh_directory.exists():
            subprocess.check_call(['sudo', 'chmod', '2770', ssh_directory])
            subprocess.check_call(['sudo', 'chmod', '2660', key_filename])

            if key_filename.exists():
                with key_filename.open('r', encoding='utf-8') as read_key_file:
                    if read_key_file.readline().rstrip('\n') == public_key:
                        return True

            subprocess.check_call(['sudo', 'rm', '-rf', ssh_directory])

        self._create_directory(agent_key, ssh_directory, user='controller')

        with key_filename.open('w', encoding='utf-8') as key_file:
            key_file.write(public_key)

        return False

    def update_permissions(self, project_key: str, agent_key: str) -> None:
        """
        Change permissions such that only the agent can access the directories.
        """

        home_directories = self.get_home_subdirectories(project_key, agent_key)
        ssh_directory = self.get_ssh_directory(agent_key)
        for directory in reversed(home_directories):
            self._update_owner(agent_key, directory)
            subprocess.check_call(['sudo', 'chmod', '2770', directory])

        key_filename = PurePath(ssh_directory, self.KEY_FILENAME)
        subprocess.check_call(['sudo', 'chmod', '2600', key_filename])
        self._update_owner(agent_key, ssh_directory)
        subprocess.check_call(['sudo', 'chmod', '2700', ssh_directory])

    def create_controller(self, project_key: str) -> None:
        """
        Create directories that the controller services use to work on the
        agent's data.
        """

        controller_path = self.get_controller_directory(project_key)
        if not Path(controller_path).exists():
            self._create_directory(project_key, controller_path,
                                   user='exporter', permissions='0770')

    def update_status_file(self, project_key: str, filename: str,
                           statuses: Union[Sequence[Mapping[str, Any]],
                                           Mapping[str, Any]]) -> None:
        """
        Update a status logging file for the agent's health monitoring.
        """

        controller_path = self.get_controller_directory(project_key)
        data_path = Path(controller_path, filename)
        if not data_path.exists():
            self._create_file(project_key, data_path, 'exporter')

        with data_path.open('a', encoding='utf-8') as data_file:
            json.dump(statuses, data_file, indent=None)
            data_file.write('\n')

    @staticmethod
    def _check_permissions(path: str, permissions: int = 0o2770) -> bool:
        try:
            mode = Path(path).stat().st_mode
        except OSError:
            return False

        if mode & 0o7777 != permissions:
            return False

        return True

    def get_permissions_status(self, project_key: str, agent_key: str) \
            -> Dict[str, Union[bool, str]]:
        """
        Check whether permissions are correct for certain paths.
        """

        if not self._check_permissions(self.get_ssh_directory(agent_key),
                                       permissions=0o2700):
            return {
                'ok': False,
                'message': 'SSH identity was not properly stored'
            }

        for path in self.get_home_subdirectories(project_key, agent_key):
            if not self._check_permissions(path):
                return {
                    'ok': False,
                    'message': 'Agent directory was not properly stored'
                }

        return {'ok': True}

def main() -> None:
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
