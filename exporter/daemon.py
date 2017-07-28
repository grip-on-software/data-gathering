"""
Internal daemon for handling agent data export and database import jobs.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from configparser import RawConfigParser
import json
import os.path
import subprocess
import Pyro4
import requests

@Pyro4.expose
class Exporter(object):
    """
    Object that starts exporter scripts.
    """

    AGENT_DIRECTORY = '/agents'
    SETTINGS_FILE = 'settings.cfg'

    def export_data(self, project_key):
        """
        Export the agent data and import it into the database.
        """

        directory = os.path.join(self.AGENT_DIRECTORY, project_key)

        subprocess.Popen(['/bin/bash', 'controller-export.sh', directory],
                         stdout=None, stderr=None, env={'CLEANUP_EXPORT': '1'})

    def start_scrape(self, project_key):
        """
        Request a Jenkins instance to start a scrape job for the remaining data.
        """

        config = RawConfigParser()
        config.read(self.SETTINGS_FILE)

        host = config.get('jenkins', 'host')
        if config.getboolean('jenkins', 'crumb'):
            crumb_data = requests.get(host + '/crumbIssuer/api/json').json()
            headers = {crumb_data['crumbRequestField']: crumb_data['crumb']}
        else:
            headers = {}

        job = config.get('jenkins', 'scrape')
        token = config.get('jenkins', 'token')
        url = '{}/job/{}/build?token={}'.format(host, job, token)
        scripts = [
            "project_sources.py", "jira_to_json.py", "history_to_json.py",
            "metric_options_to_json.py"
        ]
        payload = {
            "parameter": [
                {"name": "listOfProjects", "value": project_key},
                {"name": "importerTasks", "valie": "all,developerlink,-vcs"},
                {"name": "logLevel", "value": "INFO"},
                {"name": "cleanupRepos", "value": "true"},
                {"name": "gathererScripts", "value": " ".join(scripts)}
            ]
        }
        requests.post(url, headers=headers, data={"json": json.dumps(payload)})

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
