"""
SonarQube code quality inspection system source domain object.

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
from typing import Hashable, Optional, Union
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
        # Ensure URL ends in a slash
        if not url.endswith('/'):
            url = f'{url}/'

        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)
        self._blacklisted = Configuration.is_url_blacklisted(self.url)

    @property
    def environment(self) -> Optional[Hashable]:
        return self.plain_url

    @property
    def environment_url(self) -> Optional[str]:
        return self.plain_url

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def version(self) -> str:
        if self._blacklisted:
            return ''

        try:
            logging.info("Checking server version of %s", self.plain_url)
            verify: Union[Optional[str], bool] = self.get_option('verify')
            if verify is None:
                verify = True
            session = Session()
            session.verify = verify
            url = f'{self.url.rstrip("/")}/api/server/version'
            response = session.get(url, timeout=3)
            return response.text
        except (ConnectError, HTTPError, Timeout):
            self._blacklisted = True
            return ''
