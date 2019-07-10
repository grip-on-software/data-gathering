"""
API to perform an export of collected agent data.
"""

import cgi
import cgitb
import json
import Pyro4

def setup_log():
    """
    Set up logging.
    """

    cgitb.enable()

def main():
    """
    Main entry point.
    """

    setup_log()
    fields = cgi.FieldStorage()
    try:
        if 'project' not in fields:
            raise RuntimeError('Project must be specified')

        projects = fields.getlist('project')
        if len(projects) != 1:
            raise RuntimeError('Exactly one project must be specified in GET')

        project_key = projects[0]
        if not project_key.isupper() or not project_key.isalpha():
            raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    exporter = Pyro4.Proxy("PYRONAME:gros.exporter")
    agent_key = project_key
    if "agent" in fields:
        agent = fields.getfirst("agent")
        try:
            status = json.loads(agent)
            if "key" in status and status["key"] not in ("", "-"):
                agent_key = status["key"]
            elif "user" in status and status["user"].startswith("agent-"):
                agent_key = status["user"][len("agent-"):]
        except ValueError as error:
            print('Status: 400 Bad Request')
            print('Content-Type: text/plain')
            print()
            print(str(error))
            return

        exporter.write_agent_status(project_key, agent)

    exporter.start_scrape(project_key)
    exporter.export_data(project_key, agent_key)

    print('Status: 202 Accepted')
    print()

if __name__ == '__main__':
    main()
