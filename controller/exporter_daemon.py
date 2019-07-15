"""
Internal daemon for handling agent data export and database import jobs.
"""

import os
from pathlib import Path
import subprocess
import Pyro4
from gatherer.config import Configuration
from gatherer.jenkins import Jenkins

@Pyro4.expose
class Exporter:
    """
    Object that starts exporter scripts.
    """

    AGENT_DIRECTORY = '/agents'
    CONTROLLER_DIRECTORY = '/controller'

    def __init__(self) -> None:
        self._config = Configuration.get_settings()

    def export_data(self, project_key: str, agent_key: str) -> None:
        """
        Export the agent data and import it into the database.
        """

        directory = str(Path(self.AGENT_DIRECTORY, agent_key))

        environment = os.environ.copy()
        environment.update({
            'USER': os.getenv('USER', ''),
            'CLEANUP_EXPORT': '1'
        })
        args = ['/bin/bash', 'controller-export.sh', directory, project_key]
        subprocess.Popen(args, stdout=None, stderr=None, env=environment)

    def start_scrape(self, project_key: str) -> None:
        """
        Request a Jenkins instance to start a scrape job for the remaining data.
        """

        jenkins = Jenkins.from_config(self._config)
        job_name = self._config.get('jenkins', 'scrape')
        token = self._config.get('jenkins', 'token')
        jira_url = self._config.get('jira', 'server')
        job = jenkins.get_job(job_name)

        scripts = [
            "project_sources.py", "project_to_json.py",
            "jira_to_json.py", "history_to_json.py",
            "metric_options_to_json.py", "ldap_to_json.py"
        ]
        tasks = ["all", "developerlink", "-vcs", "-jenkins"]
        parameters = [
            {"name": "listOfProjects", "value": project_key},
            {"name": "importerTasks", "value": ",".join(tasks)},
            {"name": "logLevel", "value": "INFO"},
            {"name": "cleanupRepos", "value": "true"},
            {"name": "gathererScripts", "value": " ".join(scripts)},
            {"name": "jiraParameters", "value": "--server {}".format(jira_url)}
        ]
        job.build(parameters=parameters, token=token)

    def write_agent_status(self, project_key: str, agent_status: str) -> None:
        """
        Write status information about the agent configuration to a file in
        the controller directory.
        """

        path = Path(self.CONTROLLER_DIRECTORY, f'agent-{project_key}.json')
        with path.open('w') as agent_file:
            agent_file.write(agent_status)

def main() -> None:
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
