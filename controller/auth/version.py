"""
API to check whether an agent's version is up to date with the controller.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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
import json
import re
from gatherer import __version__ as VERSION
from gatherer.config import Configuration
from gatherer.domain.source import GitLab
from gatherer.version_control.repo import RepositorySourceException

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
                raise RuntimeError(f'Can only compare version {VERSION}')

        if not re.match('^[0-9a-f]{40}$', agent_version):
            raise RuntimeError('Version hash must be a valid commit hexsha')

        config = Configuration.get_settings()
        source = GitLab('gitlab', name='Data gathering',
                        url=f"{config.get('gitlab', 'url')}{config.get('gitlab', 'repo')}")

        try:
            repo_class = source.repository_class
            repo = repo_class(source, '../..')
            if branch != repo.default_branch:
                raise RuntimeError(f'Version must have branch {repo.default_branch}')

            local_version = repo.repo.head.commit.hexsha
            up_to_date = local_version == agent_version or \
                repo_class.is_up_to_date(source, agent_version)
        except RepositorySourceException as error:
            raise RuntimeError('Cannot detect local/remote repository') from error

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
