"""
Internal daemon for handling agent data export and database import jobs.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import os.path
import subprocess
import Pyro4
from gatherer.config import Configuration
from gatherer.jenkins import Jenkins

@Pyro4.expose
class Exporter(object):
    """
    Object that starts exporter scripts.
    """

    AGENT_DIRECTORY = '/agents'

    def __init__(self):
        self._config = Configuration.get_settings()

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

        jenkins = Jenkins.from_config(self._config)
        job_name = self._config.get('jenkins', 'scrape')
        token = self._config.get('jenkins', 'token')
        job = jenkins.get_job(job_name)

        scripts = [
            "project_sources.py", "project_to_json.py",
            "jira_to_json.py", "history_to_json.py", "metric_options_to_json.py"
        ]
        tasks = ["all", "developerlink", "-vcs", "-jenkins"]
        parameters = [
            {"name": "listOfProjects", "value": project_key},
            {"name": "importerTasks", "value": ",".join(tasks)},
            {"name": "logLevel", "value": "INFO"},
            {"name": "cleanupRepos", "value": "true"},
            {"name": "gathererScripts", "value": " ".join(scripts)}
        ]
        job.build(parameters=parameters, token=token)

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
