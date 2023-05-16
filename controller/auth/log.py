"""
API to collect log packets from an agent.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import cgi
import cgitb
import Pyro4
from gatherer.log import Log_Setup

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
