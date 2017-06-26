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
import grp
import json
import os
import pwd

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

    uid = pwd.getpwnam("exporter").pw_uid
    gid = grp.getgrnam("controller").gr_gid

    controller_path = os.path.join('/controller', project_key)
    if not os.path.exists(controller_path):
        os.mkdir(controller_path, 0770)
        os.chown(controller_path, uid, gid)

    data_filename = os.path.join(controller_path, 'data_status.json')
    if not os.path.exists(data_filename):
        os.mknod(data_filename, 0660)
        os.chown(data_filename, uid, gid)

    with open(data_filename, 'a') as data_file:
        json.dump(statuses, data_file, indent=None)
        data_file.write('\n')

    print('Status: 202 Accepted')
    print()

if __name__ == '__main__':
    main()
