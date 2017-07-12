"""
Internal daemon for handling agent data export and database import jobs.
"""

import os.path
import subprocess
import Pyro4

@Pyro4.expose
# pylint: disable=too-few-public-methods
class Exporter(object):
    """
    Object that starts exporter scripts.
    """

    AGENT_DIRECTORY = '/agents'

    def export_data(self, project_key):
        """
        Export the agent data and import it into the database.
        """

        directory = os.path.join(self.AGENT_DIRECTORY, project_key)

        subprocess.Popen(['/bin/bash', 'controller-export.sh', directory],
                         stdout=None, stderr=None, env={'CLEANUP_EXPORT': '1'})

def main():
    """
    Main setup and event loop.
    """

    daemon = Pyro4.Daemon()
    object_name_server = Pyro4.locateNS()
    uri = daemon.register(Exporter)
    object_name_server.register("gros.exporter", uri)

    daemon.requestLoop()

if __name__ == "__main__":
    main()
