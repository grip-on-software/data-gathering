"""
Internal daemon for handling agent data export and database import jobs.
"""

import subprocess
import Pyro4

@Pyro4.expose
class Exporter(object):
    """
    Object that starts exporter scripts.
    """

    def export_data(self, directory):
        """
        Export the agent data and import it into the database.
        """

        subprocess.Popen(['/bin/bash', 'controller-export.sh', directory],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

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
