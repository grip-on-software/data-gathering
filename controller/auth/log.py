"""
API to collect log packets from an agent.
"""

import cgi
import cgitb
import Pyro4
from gatherer.log import Log_Setup

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

        packet = {}
        for key in fields.keys():
            if key != 'project':
                packet[key] = fields.getfirst(key)

        if not packet:
            raise RuntimeError('No logging parameters were provided')
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    if 'message' in packet and Log_Setup.is_ignored(packet['message']):
        print('Status: 204 No Content')
        print()
        return

    controller = Pyro4.Proxy("PYRONAME:gros.controller")
    controller.create_controller(project_key)
    controller.update_status_file(project_key, 'log.json', packet)

    print('Status: 202 Accepted')
    print()

if __name__ == '__main__':
    main()
