"""
API to encrypt a given field.
"""

import cgi
import cgitb
import json
import sys
import Pyro4

def setup_log() -> None:
    """
    Set up logging.
    """

    cgitb.enable()

def main() -> None:
    """
    Main entry point.
    """

    setup_log()
    fields = cgi.FieldStorage()
    project_key = ''
    try:
        if 'project' in fields:
            projects = fields.getlist('project')
            if len(projects) != 1:
                raise RuntimeError('At most one project must be specified in GET')

            project_key = projects[0]
            if not project_key.isupper() or not project_key.isalpha():
                raise RuntimeError('Project key must be all-uppercase, only alphabetic characters')

        if 'value' not in fields:
            raise RuntimeError('Value must be provided')

        values = fields.getlist('value')
        if len(values) != 1:
            raise RuntimeError('Exactly one value must be provided')

        value = values[0]
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

    gatherer = Pyro4.Proxy("PYRONAME:gros.gatherer")
    encrypted_value = gatherer.encrypt(project_key, value)
    if encrypted_value == '':
        print('Status: 404 Not Found')
        print('Content-Type: text/plain')
        print()
        print('The value could not be encrypted for the provided project')
        return

    print('Content-Type: application/json')
    print()
    json.dump({
        "value": encrypted_value,
        "encryption": 2 if project_key == '' else 1
    }, sys.stdout)

if __name__ == "__main__":
    main()
