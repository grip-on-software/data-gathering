"""
GitLab source domain object.

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

import logging
from typing import Hashable, List, Optional, Tuple, Type
from urllib.parse import quote_plus, urlsplit, SplitResult
from gitlab import Gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError, \
    GitlabListError
from requests.exceptions import ConnectionError as ConnectError, Timeout
from ...config import Configuration
from ...request import Session
from .types import Source, Source_Types, Project
from .git import Git
from ...git.gitlab import GitLab_Repository

@Source_Types.register('gitlab')
@Source_Types.register('git',
                       lambda cls, follow_host_change=True, url='', **data: \
                       cls.is_gitlab_url(url,
                                         follow_host_change=follow_host_change))
class GitLab(Git):
    """
    GitLab source repository.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        self._gitlab_host: str = ''
        self._gitlab_token: Optional[str] = None
        self._gitlab_namespace: str = ''
        self._gitlab_group: Optional[str] = None
        self._gitlab_path: str = ''
        self._gitlab_api: Optional[Gitlab] = None

        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)

    @classmethod
    def is_gitlab_url(cls, url: str, follow_host_change: bool = True) -> bool:
        """
        Check whether a given URL is part of a GitLab instance for which we have
        credentials.
        """

        parts = urlsplit(cls._alter_git_url(url))
        return cls.is_gitlab_host(cls._format_host_section(parts),
                                  follow_host_change=follow_host_change)

    @classmethod
    def is_gitlab_host(cls, host: str, follow_host_change: bool = True) -> bool:
        """
        Check whether a given host (without scheme part) is a GitLab host for
        which we have credentials.
        """

        if follow_host_change:
            host = cls._get_changed_host(host)

        return cls._has_gitlab_token(host)

    @classmethod
    def _has_gitlab_token(cls, host: str) -> bool:
        return cls.has_option(host, 'gitlab_token')

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super()._update_credentials()
        orig_host = orig_parts.netloc

        # Check which group to use in the GitLab API.
        if self.has_option(orig_host, 'group'):
            self._gitlab_group = self._credentials.get(orig_host, 'group')

        # Retrieve the actual namespace of the source.
        path = orig_parts.path.strip('/')
        if self.has_option(host, 'strip'):
            # Use the strip path to add the web base URL and remove from the
            # provided URL path.
            host_path = self._credentials.get(host, 'strip')
            if path.startswith(host_path):
                path = path[len(host_path):].lstrip('/')
        else:
            host_path = ''

        path_parts = path.split('/', 1)
        self._gitlab_namespace = path_parts[0]

        # Check whether the host was changed and a custom gitlab group exists
        # for this host change.
        if self._follow_host_change and host != orig_host:
            path = self._update_group_url(path)

        # Find the GitLab token and URL without authentication for connecting
        # to the GitLab API.
        if self._has_gitlab_token(host):
            self._gitlab_token = self._credentials.get(host, 'gitlab_token')

        scheme = self._get_web_protocol(host, orig_parts.scheme)

        self._gitlab_host = self._create_url(scheme, host, host_path, '', '')
        self._gitlab_path = self.remove_git_suffix(path)

        self._url = self.url.rstrip('/')

        return orig_parts, host

    def _update_group_url(self, repo_path: str) -> str:
        if self._gitlab_group is None:
            return repo_path
        if self._gitlab_namespace == self._gitlab_group:
            return repo_path

        # Parse the current URL to update its path.
        url_parts = urlsplit(self._url)
        repo_path_name = repo_path.split('/', 1)[1]
        path = f'{self._gitlab_group}/{self._gitlab_namespace}-{repo_path_name}'
        # Track the new namespace and use the new URL.
        self._gitlab_namespace = self._gitlab_group
        self._url = self._create_url(url_parts.scheme, url_parts.netloc, path,
                                     url_parts.query, url_parts.fragment)
        return path

    @property
    def repository_class(self) -> Type[GitLab_Repository]:
        return GitLab_Repository

    @property
    def environment(self) -> Optional[Hashable]:
        return (self._gitlab_host, self._gitlab_group, self._gitlab_namespace)

    @property
    def environment_type(self) -> str:
        return 'gitlab'

    @property
    def environment_url(self) -> Optional[str]:
        if self._gitlab_group is not None:
            return f'{self._gitlab_host}/{self._gitlab_group}'

        return f'{self._gitlab_host}/{self._gitlab_namespace}'

    @property
    def web_url(self) -> Optional[str]:
        return f'{self._gitlab_host}/{self._gitlab_path}'

    @property
    def host(self) -> str:
        """
        Retrieve the host name with scheme part of the GitLab instance.

        This is the base URL after following host changes.
        """

        return self._gitlab_host

    @property
    def version(self) -> str:
        try:
            self.gitlab_api.timeout = 3
            version = str(self.gitlab_api.version()[0])
        except RuntimeError:
            version = ''
        finally:
            if self._gitlab_api is not None:
                self.gitlab_api.timeout = None

        if version == 'unknown':
            return ''

        return version

    @property
    def gitlab_token(self) -> Optional[str]:
        """
        Retrieve the token that is used for authenticating in the GitLab API.
        """

        return self._gitlab_token

    @property
    def gitlab_group(self) -> Optional[str]:
        """
        Retrieve the custom gitlab group used on the GitLab instance.

        If this is `None`, then there is no custom group for this source.
        The caller should fall back to the project long name or some other
        information it has.

        Note that this group is instance-wide, and may not actually be the group
        that this source repository is in. Instead it is used for group URL
        updates and gitlab source queries. See `gitlab_namespace` for the
        group or namespace of the source object.
        """

        return self._gitlab_group

    @property
    def gitlab_namespace(self) -> str:
        """
        Retrieve the namespace in which the source exists.
        """

        return self._gitlab_namespace

    @property
    def gitlab_path(self) -> str:
        """
        Retrieve the path used in the GitLab API. This is the final path after
        following group URL updates. The path includes the namespace, usually
        the same as the group, and the repository name. The path is URL-encoded
        for use in parameters.

        The path can be used in API project calls to retrieve the project by its
        unique path identifier.
        """

        return quote_plus(self._gitlab_path)

    @property
    def gitlab_api(self) -> Gitlab:
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        if Configuration.is_url_blacklisted(self.host):
            raise RuntimeError(f'GitLab API for {self.host} is blacklisted')

        if self._gitlab_api is None:
            unsafe = self.get_option('unsafe_hosts')
            session = Session(verify=unsafe is None)
            try:
                logging.info('Setting up API for %s', self.host)
                self._gitlab_api = Gitlab(self.host,
                                          private_token=self.gitlab_token,
                                          session=session,
                                          timeout=3)
                self._gitlab_api.auth()
                self._gitlab_api.timeout = None
            except (ConnectError, Timeout, GitlabAuthenticationError, GitlabGetError) as error:
                self._gitlab_api = None
                raise RuntimeError('Cannot access the GitLab API') from error

        return self._gitlab_api

    def check_credentials_environment(self) -> bool:
        if self._gitlab_group is None:
            return True

        return self._gitlab_group == self._gitlab_namespace

    def get_sources(self) -> List[Source]:
        # pylint: disable=no-member
        if self.gitlab_group is not None:
            group_name = self.gitlab_group
        else:
            group_name = self.gitlab_namespace

        try:
            group = self.gitlab_api.groups.get(group_name, lazy=True)
        except (GitlabAuthenticationError, GitlabGetError):
            logging.warning('GitLab group %s is not accessible', group_name)
            return super().get_sources()

        # Fetch the group projects by requesting the group to the API again.
        group_repos = group.projects.list()

        logging.info('%s has %d repos: %s', group_name, len(group_repos),
                     ', '.join([repo.name for repo in group_repos]))

        sources = []
        for project_repo in group_repos:
            repo_name = project_repo.name
            project = self.gitlab_api.projects.get(project_repo.get_id(),
                                                   lazy=True)
            try:
                if not project.commits.list(per_page=1, all=False):
                    logging.info('Ignoring empty GitLab repository %s',
                                 repo_name)
                    continue
            except (GitlabAuthenticationError, GitlabListError):
                logging.warning('GitLab repository %s is not accessible',
                                repo_name)
                continue

            url = self.remove_git_suffix(project_repo.http_url_to_repo)
            source = Source.from_type('gitlab', name=repo_name, url=url,
                                      follow_host_change=False)

            sources.append(source)

        return sources

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        if self.gitlab_token is None:
            raise RuntimeError(f'GitLab source {self.host} has no API token')

        title = f'GROS agent for the {project.key} project'
        for key in self.gitlab_api.user.keys.list(as_list=False):
            if key.key == public_key:
                logging.info('SSH key already exists on GitLab host %s.',
                             self.host)
                return

            if key.title == title:
                logging.info('Removing old SSH key "%s" on GitLab host %s...',
                             key.title, self.host)
                if not dry_run:
                    key.delete()

        logging.info('Adding new SSH key "%s" to GitLab host %s...', title,
                     self.host)
        if not dry_run:
            self.gitlab_api.user.keys.create({
                'title': title,
                'key': public_key
            })
