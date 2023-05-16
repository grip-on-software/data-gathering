"""
GitHub source domain object.

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

from typing import Dict, Hashable, List, Optional, Tuple, Type
from urllib.parse import urlsplit, SplitResult
import logging
import github
import github.Repository
from .types import Source, Source_Types
from .git import Git
from ...git.github import GitHub_Repository

@Source_Types.register('github')
@Source_Types.register('git',
                       lambda cls, url='', **data: \
                            cls.is_github_url(url))
class GitHub(Git):
    """
    GitHub source repository.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True, **kwargs: str) -> None:
        self._github_url: str = ''
        self._github_token: Optional[str] = None
        self._github_api: Optional[github.Github] = None
        self._github_api_url: str = github.MainClass.DEFAULT_BASE_URL
        self._github_owner: str = ''
        self._github_repo: Optional[github.Repository.Repository] = None
        self._github_team: Optional[str] = kwargs.pop('github_team', None)

        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)

    @classmethod
    def is_github_url(cls, url: str) -> bool:
        """
        Check whether a given URL is part of a GitHub instance for which we have
        credentials.
        """

        parts = urlsplit(cls._alter_git_url(url))
        return cls.is_github_host(cls._format_host_section(parts))

    @classmethod
    def is_github_host(cls, host: str) -> bool:
        """
        Check whether a given host (without scheme part) is a GitHub host for
        which we have credentials.
        """

        return cls.has_option(host, 'github_token')

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super()._update_credentials()

        # Retrieve the owner from the URL of the source.
        path = orig_parts.path.lstrip('/')
        path_parts = path.split('/', 1)
        self._github_owner = path_parts[0]
        scheme = self._get_web_protocol(host, orig_parts.scheme,
                                        default_scheme='https')
        self._github_url = self._create_url(scheme, host, '', '', '')

        if self.is_github_host(host):
            self._github_token = self._credentials.get(host, 'github_token')
        if self.has_option(host, 'github_api_url'):
            self._github_api_url = self._credentials.get(host, 'github_api_url')

        return orig_parts, host

    @property
    def repository_class(self) -> Type[GitHub_Repository]:
        return GitHub_Repository

    @property
    def environment(self) -> Optional[Hashable]:
        return (self._host, self.github_owner, self.github_team)

    @property
    def environment_type(self) -> str:
        return 'github'

    @property
    def environment_url(self) -> Optional[str]:
        return f'{self._github_url}/{self.github_owner}'

    @property
    def web_url(self) -> Optional[str]:
        return f'{self._github_url}/{self.github_owner}/{self.path_name}'

    @property
    def github_token(self) -> Optional[str]:
        """
        Retrieve the token that is used for authenticating in the GitHub API.
        """

        return self._github_token

    @property
    def github_owner(self) -> str:
        """
        Retrieve the user or organization which owns source's repository.
        """

        return self._github_owner

    @property
    def github_team(self) -> Optional[str]:
        """
        Retrieve the team that manages this source's repository, or `None` if
        there is no team known.
        """

        return self._github_team

    @property
    def github_repo(self) -> github.Repository.Repository:
        """
        Retrieve the repository information from the GitHub API for this
        source's repository.
        """

        if self._github_repo is None:
            full_path = f'{self._github_owner}/{self.path_name}'
            self._github_repo = self.github_api.get_repo(full_path)

        return self._github_repo

    @property
    def github_api(self) -> github.Github:
        """
        Retrieve an instance of the GitHub API connection.
        """

        if self._github_api is None:
            logging.info('Setting up GitHub API')
            unsafe = self.get_option('unsafe_hosts')
            self._github_api = github.Github(self.github_token,
                                             base_url=self._github_api_url,
                                             verify=not unsafe)

        return self._github_api

    def get_sources(self) -> List[Source]:
        if self._github_team is None:
            user = self.github_api.get_user(self._github_owner)
            repos = user.get_repos()
        else:
            org = self.github_api.get_organization(self._github_owner)
            team = None
            for team in org.get_teams():
                if team.slug == self._github_team:
                    break
            else:
                msg = "Cannot find team '{}' in organization '{}'"
                raise RuntimeError(msg.format(self._github_team,
                                              self._github_owner))

            repos = team.get_repos()

        sources = []
        for repo in repos:
            source = Source.from_type('github',
                                      name=repo.name,
                                      url=repo.clone_url,
                                      github_team=self._github_team,
                                      github_repo=repo)
            sources.append(source)

        return sources

    def export(self) -> Dict[str, str]:
        data = super().export()
        if self._github_team is not None:
            data['github_team'] = self._github_team

        return data
