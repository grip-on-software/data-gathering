"""
Internal daemon for handling update tracking and project salt requests,
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import os.path
import Pyro4
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.salt import Salt
from gatherer.update import Database_Tracker

@Pyro4.expose
class Gatherer(object):
    """
    Object that updates the agent directory and retrieves salts.
    """

    def __init__(self):
        self._config = Configuration.get_settings()

    def get_update_trackers(self, project_key, home_directory):
        """
        Retrieve update tracking files and store them in the agent's update
        directory.
        """

        export_directory = os.path.join(home_directory, 'export')
        update_directory = os.path.join(home_directory, 'update')

        project = Project(project_key,
                          export_directory=export_directory,
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
