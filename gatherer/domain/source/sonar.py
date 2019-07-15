"""
SonarQube code quality inspection system source domain object.
"""

import logging
from typing import Hashable, Optional
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from ...config import Configuration
from ...request import Session
from .types import Source, Source_Types, Project

@Source_Types.register('sonar')
class Sonar(Source):
    """
    SonarQube source.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)
        self._blacklisted = Configuration.is_url_blacklisted(self.url)

    @property
    def environment(self) -> Optional[Hashable]:
        return self.url

    @property
    def environment_url(self) -> Optional[str]:
        return self.url

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def version(self) -> str:
        if self._blacklisted:
            return ''

        try:
            logging.info("Checking server version of %s", self.url)
            session = Session()
            url = '{}/api/server/version'.format(self.url.rstrip('/'))
            response = session.get(url, timeout=3)
            return response.text
        except (ConnectError, HTTPError, Timeout):
            self._blacklisted = True
            return ''
