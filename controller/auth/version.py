"""
API to check whether an agent's version is up to date with the controller.
"""

import cgi
import cgitb
import json
import re
from gatherer import __version__ as VERSION
from gatherer.config import Configuration
from gatherer.domain import Source
from gatherer.version_control.repo import RepositorySourceException

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

        agent_version = versions[0]
        branch = 'master'
        if '-' in agent_version:
            version_parts = agent_version.split('-')
            gatherer_version = version_parts[0]
            branch = '-'.join(version_parts[1:-1])
            agent_version = version_parts[-1]

            if gatherer_version != VERSION:
                raise RuntimeError('Can only compare version {}'.format(VERSION))

        if not re.match('^[0-9a-f]{40}$', agent_version):
            raise RuntimeError('Version hash must be a valid commit hexsha')

        config = Configuration.get_settings()
        source = Source.from_type('gitlab', name='Data gathering',
                                  url=config.get('gitlab', 'url') + config.get('gitlab', 'repo'))
        try:
            repo = source.repository_class(source, '../..')
            if branch != repo.default_branch:
                raise RuntimeError('Version must have branch {}'.format(repo.default_branch))

            local_version = repo.repo.head.commit.hexsha
            up_to_date = local_version == agent_version or \
                source.repository_class.is_up_to_date(source, agent_version)
        except RepositorySourceException:
            raise RuntimeError('Cannot detect local/remote repository')

        print('Status: 200 OK')
        print('Content-Type: application/json')
        print()
        print(json.dumps({
            'up_to_date': up_to_date,
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
