"""
API to track dashboard status.
"""

from __future__ import print_function
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

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

        if 'status' not in fields:
            raise RuntimeError('Status must be provided')

        status = fields.getlist('status')
        if len(status) != 1:
            raise RuntimeError('Exactly one status field must be specified')

        try:
            statuses = json.loads(status[0])
        except ValueError:
            raise RuntimeError('Status field must be valid JSON')
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    controller = Pyro4.Proxy("PYRONAME:gros.controller")
    controller.create_controller(project_key)
    controller.update_status(project_key, statuses)

    print('Status: 202 Accepted')
    print()

if __name__ == '__main__':
    main()
