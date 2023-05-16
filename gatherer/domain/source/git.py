"""
Git source domain object.

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

import re
from urllib.parse import SplitResult
from typing import Optional, Tuple, Type
from .types import Source, Source_Types, Project
from ...git import Git_Repository

@Source_Types.register('git')
class Git(Source):
    """
    Git source repository.
    """

    GIT_URL_REGEX = re.compile(r'(?P<netloc>[^@]+@[^:]+):/?(?P<path>.+)')

    @classmethod
    def _alter_git_url(cls, url: str) -> str:
        # Normalize git suffix
        if url.endswith('.git/'):
            url = url.rstrip('/')

        # Convert short SCP-like URLs to full SSH protocol URLs so that the
        # parsing done by the superclass can completely understand the URL.
        match = cls.GIT_URL_REGEX.match(url)
        if match:
            groups = match.groupdict()
            return f'ssh://{groups["netloc"]}/{groups["path"]}'

        return url

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        self._plain_url = self._alter_git_url(self._plain_url)
        return super()._update_credentials()

    def _format_ssh_url(self, hostname: str, auth: str, port: Optional[int],
                        path: str) -> str:
        # Use either short SCP-like URL or long SSH URL
        if port is not None:
            return super()._format_ssh_url(hostname, auth, port, path)

        return f'{auth}:{path}'

    @property
    def repository_class(self) -> Type[Git_Repository]:
        return Git_Repository

    @property
    def path_name(self) -> str:
        path_name = self.get_path_name(self.url)
        if path_name is None:
            return super().path_name

        return path_name

    @classmethod
    def get_path_name(cls, url: str) -> Optional[str]:
        """
        Retrieve the repository name from a `url` or `None` if not possible.
        """

        parts = url.split('/')
        if len(parts) <= 1:
            return None

        # Handle URLs ending in slashes
        repo = parts[-1]
        if repo == '':
            repo = parts[-2]

        # Remove .git from repository name
        return cls.remove_git_suffix(repo)

    @staticmethod
    def remove_git_suffix(repo: str) -> str:
        """
        Remove the '.git' suffix from a repository name as it frequently
        occurs in the URL slug of that repository.
        """

        if repo.endswith('.git'):
            repo = repo[:-len('.git')]

        return repo

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
