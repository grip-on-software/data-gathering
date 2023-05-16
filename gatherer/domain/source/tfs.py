"""
Team Foundation Server domain object.

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
from urllib.parse import unquote, urlsplit, SplitResult
from requests.exceptions import ConnectionError as ConnectError, Timeout
from .types import Source, Source_Types
from .git import Git
from ...git.tfs import TFS_Repository, TFS_Project, TFVC_Project
from ...config import Configuration

TFS_Collection = Tuple[str, ...]

@Source_Types.register('tfs')
@Source_Types.register('git',
                       lambda cls, follow_host_change=True, url='', **data: \
                       cls.is_tfs_url(url,
                                      follow_host_change=follow_host_change))
class TFS(Git):
    """
    Team Foundation Server source repository using Git.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        self._tfs_host: str = ''
        self._tfs_collections: TFS_Collection = ('',)
        self._tfs_repo: Optional[str] = None
        self._tfs_user: str = ''
        self._tfs_password: str = ''
        self._tfs_api: Optional[TFS_Project] = None

        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)

    @classmethod
    def is_tfs_url(cls, url: str, follow_host_change: bool = True) -> bool:
        """
        Check whether a given URL is part of a TFS instance.
        """

        parts = urlsplit(url)
        return cls.is_tfs_host(parts.netloc,
                               follow_host_change=follow_host_change)

    @classmethod
    def is_tfs_host(cls, host: str, follow_host_change: bool = True) -> bool:
        """
        Check whether a given host (without scheme part) is a TFS host.
        """

        if follow_host_change:
            host = cls._get_changed_host(host)

        return cls.has_option(host, 'tfs')

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super()._update_credentials()

        # Ensure we have a HTTP/HTTPS URL to the web host for API purposes.
        # This includes altering the web port to the one that TFS listens to.
        scheme = self._get_web_protocol(host, orig_parts.scheme)
        if self.has_option(host, 'web_port'):
            hostname = self._get_host_parts(host, orig_parts)[0]
            web_port = self._credentials.get(host, 'web_port')
            web_host = f'{hostname}:{web_port}'
        else:
            web_host = host

        self._tfs_host = self._create_url(scheme, web_host, '', '', '')

        # Retrieve the TFS collection
        path = orig_parts.path.lstrip('/')
        path_parts = path.split('/_git/', 1)
        tfs_path = path_parts[0]
        if len(path_parts) > 1:
            self._tfs_repo = path_parts[1].rstrip('/')

        tfs_parts = tfs_path.split('/')
        num_parts = 2 if tfs_parts[0] == 'tfs' else 1
        if len(tfs_parts) > num_parts:
            collection = '/'.join(tfs_parts[:num_parts])
            self._tfs_collections = (collection, tfs_parts[num_parts])
        else:
            self._tfs_collections = (tfs_path,)

        # Store credentials separately to provide to the API.
        self._tfs_user = self._credentials.get(host, 'username')
        self._tfs_password = self._credentials.get(host, 'password')

        url_parts = urlsplit(self.url)
        if url_parts.scheme == self.SSH_PROTOCOL and \
            url_parts.username is not None and url_parts.hostname is not None:
            # Do not use a port specifier.
            netloc = f'{url_parts.username}{"@"}{url_parts.hostname}'
        else:
            netloc = url_parts.netloc

        # Remove trailing slashes since they are optional and the TFS API
        # returns remote URLs without slashes.
        # Also lowercase the path to match insensitively (as TFS does).
        self._url = self._create_url(url_parts.scheme, netloc,
                                     url_parts.path.rstrip('/').lower(), '', '')

        return orig_parts, host

    @property
    def repository_class(self) -> Type[TFS_Repository]:
        return TFS_Repository

    @property
    def environment(self) -> Optional[Hashable]:
        return (self._tfs_host,) + tuple(collection.lower() for collection in self._tfs_collections)

    @property
    def environment_type(self) -> str:
        return 'tfs'

    @property
    def environment_url(self) -> str:
        return f'{self._tfs_host}/{"/".join(self._tfs_collections)}'

    @property
    def web_url(self) -> Optional[str]:
        if self._tfs_repo is None:
            return self.environment_url

        return f'{self.environment_url}/{self._tfs_repo}'

    @property
    def tfs_api(self) -> TFS_Project:
        """
        Retrieve an instance of the TFS API connection for the TFS collection
        on this host.
        """

        if Configuration.is_url_blacklisted(self._tfs_host):
            raise RuntimeError(f'TFS API for {self._tfs_host} is blacklisted')

        if self._tfs_api is None:
            logging.info('Setting up API for %s', self._tfs_host)
            self._tfs_api = TFS_Project(self._tfs_host, self._tfs_collections,
                                        unquote(self._tfs_user),
                                        self._tfs_password)

        return self._tfs_api

    @property
    def tfs_collections(self) -> TFS_Collection:
        """
        Retrieve the collection path and optionally project name for the source.
        The value is either a tuple with one or two elements.
        The first element of the tuple is the collection path, joined with
        slashes, and the second element if available is the project name,
        which is left out if the collection already provides unique
        identification for the TFS project.
        """

        return self._tfs_collections

    @property
    def tfs_repo(self) -> Optional[str]:
        """
        Retrieve the repository name from the TFS URL.
        """

        return self._tfs_repo

    def _format_url(self, url: str) -> str:
        parts = urlsplit(url)
        return self._create_url(parts.scheme, self._host, parts.path,
                                parts.query, parts.fragment)

    def check_credentials_environment(self) -> bool:
        tfs_collection = self.get_option('tfs')
        if tfs_collection is None or tfs_collection == 'true':
            return True

        return '/'.join(self._tfs_collections).lower().startswith(tfs_collection.lower())

    def get_sources(self) -> List[Source]:
        sources: List[Source] = []
        try:
            repositories = self.tfs_api.repositories()
        except (RuntimeError, ConnectError, Timeout):
            logging.exception('Could not set up TFS API')
            return sources

        for repository in repositories:
            url = self._format_url(repository['remoteUrl'])
            source = Source.from_type('tfs', name=repository['name'], url=url,
                                      follow_host_change=False)
            sources.append(source)

        return sources

@Source_Types.register('tfvc')
class TFVC(TFS):
    """
    Team Foundation Server source repository using TFVC.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)
        self._tfvc_project: str = ''

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super()._update_credentials()

        self._tfvc_project = self._tfs_collections[-1]
        if len(self._tfs_collections) == 1:
            self._tfs_collections = ('', self._tfvc_project)

        return orig_parts, host

    @property
    def tfvc_project(self) -> str:
        """
        Retrieve the project name of the TFVC repository.
        """

        return self._tfvc_project

    @property
    def tfs_api(self) -> TFS_Project:
        """
        Retrieve an instance of the TFS API connection for the TFS collection
        on this host.
        """

        if Configuration.is_url_blacklisted(self._tfs_host):
            raise RuntimeError(f'TFS API for {self._tfs_host} is blacklisted')

        if self._tfs_api is None:
            logging.info('Setting up API for %s', self._tfs_host)
            self._tfs_api = TFVC_Project(self._tfs_host, self._tfs_collections,
                                         unquote(self._tfs_user),
                                         self._tfs_password)

        return self._tfs_api

    @property
    def environment_url(self) -> str:
        path = '/'.join(part for part in self._tfs_collections if part != '')
        return f'{self._tfs_host}/{path}'

    def get_sources(self) -> List[Source]:
        sources: List[Source] = []
        try:
            if not isinstance(self.tfs_api, TFVC_Project):
                raise RuntimeError('Expected TFVC API')

            projects = self.tfs_api.projects()
        except (RuntimeError, ConnectError, Timeout):
            logging.exception('Could not set up TFVC API')
            return sources

        for project in projects:
            collection = f'{self._tfs_collections[0]}/' \
                if self._tfs_collections[0] else ''
            url = f'{self._tfs_host}/{collection}{project["name"]}'
            name = project.get('description', project['name'])
            source = Source.from_type('tfvc', name=name,
                                      url=url, follow_host_change=False)
            sources.append(source)

        return sources
