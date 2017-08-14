"""
Internal daemon for handling update tracking and project salt requests,
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import json
import os.path
import pymonetdb
import Pyro4
from gatherer.config import Configuration
from gatherer.database import Database
from gatherer.domain import Project
from gatherer.files import File_Store
from gatherer.salt import Salt
from gatherer.update import Database_Tracker

@Pyro4.expose
class Gatherer(object):
    """
    Object that updates the agent directory and retrieves salts.
    """

    def __init__(self):
        self._config = Configuration.get_settings()

    def get_database_status(self, project_key):
        """
        Retrieve status information from the database related to its
        availability and acceptance of new results.
        """

        try:
            database = Database(user=self._config.get('database', 'username'),
                                password=self._config.get('database', 'password'),
                                host=self._config.get('database', 'host'),
                                database=self._config.get('database', 'name'))
        except (EnvironmentError, pymonetdb.Error) as error:
            return {
                'ok': False,
                'message': str(error)
            }

        if database.get_project_id(project_key) is None:
            return {
                'ok': False,
                'message': 'Project is not yet registered in the database'
            }

        return {'ok': True}

    def get_update_trackers(self, project_key, home_directory):
        """
        Retrieve update tracking files and store them in the agent's update
        directory.
        """

        # Put all update trackers in a separate directory.
        update_directory = os.path.join(home_directory, 'update')

        project = Project(project_key,
                          export_directory=update_directory,
                          update_directory=update_directory)
        track = Database_Tracker(project,
                                 user=self._config.get('database', 'username'),
                                 password=self._config.get('database', 'password'),
                                 host=self._config.get('database', 'host'),
                                 database=self._config.get('database', 'name'))
        track.retrieve()

    def get_salts(self, project_key):
        """
        Retrieve project-specific encryption salts.
        """

        project = Project(project_key)
        salt = Salt(project,
                    user=self._config.get('database', 'username'),
                    password=self._config.get('database', 'password'),
                    host=self._config.get('database', 'host'),
                    database=self._config.get('database', 'name'))
        return salt.execute()

    def get_usernames(self, project_key):
        """
        Retrieve username patterns that need to be replaced before encryption.
        """

        store_type = File_Store.get_type(self._config.get('dropins', 'type'))
        store = store_type(self._config.get('dropins', 'url'))
        store.login(self._config.get('dropins', 'username'),
                    self._config.get('dropins', 'password'))

        data_file = 'data_vcsdev_to_dev.json'
        usernames_file = store.get_file_contents('import/{}'.format(data_file))
        patterns = json.loads(usernames_file)
        usernames = []
        for pattern in patterns:
            if 'projects' in pattern and project_key in pattern['projects']:
                del pattern['projects']
                usernames.append(pattern)

        return usernames

def main():
    """
    Main setup and event loop.
    """

    daemon = Pyro4.Daemon()
    object_name_server = Pyro4.locateNS()
    uri = daemon.register(Gatherer)
    object_name_server.register("gros.gatherer", uri)

    daemon.requestLoop()

if __name__ == "__main__":
    main()
