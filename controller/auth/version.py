"""
API to check whether an agent's version is up to date with the controller.
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
import re
import git

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
        if 'version' not in fields:
            raise RuntimeError('Version must be specified')

        versions = fields.getlist('version')
        if len(versions) != 1:
            raise RuntimeError('Exactly one version must be specified')

        version = versions[0]
        if '-' in version:
            version = version.split('-')[-1]

        if not re.match('^[0-9a-f]{40}$', version):
            raise RuntimeError('Version hash must a valid commit hexsha')

        try:
            repo = git.Repo('../..')
        except git.exc.InvalidGitRepositoryError:
            raise RuntimeError('Cannot detect local repository')

        local_version = repo.head.commit.hexsha

        print('Status: 200 OK')
        print('Content-Type: application/json')
        print()
        print(json.dumps({
            'up_to_date': local_version == version,
            'version': local_version
        }))
    except RuntimeError as error:
        print('Status: 400 Bad Request')
        print('Content-Type: text/plain')
        print()
        print(str(error))
        return

if __name__ == '__main__':
    main()
