"""
Jira issue tracker source domain object.
"""

from typing import Hashable, Optional, Tuple
from urllib.parse import urlsplit, SplitResult, unquote
from jira import JIRA
from jira.exceptions import JIRAError
from .types import Source, Source_Types, Project
from ...config import Configuration

@Source_Types.register('jira')
class Jira(Source):
    """
    Jira source.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True, **kwargs: str) -> None:
        self._username: Optional[str] = kwargs.pop('username', None)
        self._password: Optional[str] = kwargs.pop('password', None)
        self._agile_path = str(JIRA.DEFAULT_OPTIONS["agile_rest_path"])
        self._jira_api: Optional[JIRA] = None
        self._version: Optional[str] = None

        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)

        self._plain_url = self._plain_url.strip('/')

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super(Jira, self)._update_credentials()
        if self.has_option(host, 'agile_rest_path'):
            self._agile_path = self._credentials.get(host, 'agile_rest_path')

        return orig_parts, host

    @property
    def environment(self) -> Optional[Hashable]:
        return self.environment_url

    @property
    def environment_url(self) -> Optional[str]:
        return self.plain_url

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def version(self) -> str:
        if self._version is None:
            try:
                self._version = str(self.jira_api.server_info()['version'])
            except (RuntimeError, JIRAError, KeyError):
                self._version = ''

        return self._version

    @property
    def jira_agile_path(self) -> str:
        """
        Retrieve the REST path to use for JIRA Agile requests.
        """

        return self._agile_path

    @property
    def jira_api(self) -> JIRA:
        """
        Retrieve the JIRA API object for this source.
        """

        if Configuration.is_url_blacklisted(self.url):
            raise RuntimeError('JIRA API for {} is blacklisted'.format(self.plain_url))

        if self._jira_api is None:
            options = {
                "server": self.plain_url,
                "agile_rest_path": self._agile_path
            }

            parts = urlsplit(self.url)
            auth: Optional[Tuple[str, Optional[str]]] = None
            if parts.username is not None and parts.passwd is not None:
                auth = (unquote(parts.username), unquote(parts.password))
            elif self._username is not None:
                auth = (self._username, self._password)

            self._jira_api = JIRA(options, basic_auth=auth, max_retries=0)

        return self._jira_api
