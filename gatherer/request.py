"""
Module that provides HTTP request sessions.

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

from pathlib import Path
from typing import Optional, Union
import requests
from requests.auth import AuthBase
from requests.models import Response
from . import __name__ as _gatherer_name, __version__ as _gatherer_version

class Session(requests.Session):
    """
    HTTP request session.

    This provides options to change verification and authentication settings
    for the session, and sets an appropriate user agent.
    """

    def __init__(self, verify: Union[bool, str] = True,
                 auth: Optional[AuthBase] = None) -> None:
        super().__init__()

        user_agent = self.headers['User-Agent'] \
            if isinstance(self.headers['User-Agent'], str) \
            else str(self.headers['User-Agent'], encoding='utf-8')
        self.headers['User-Agent'] = f'{user_agent} {self._get_user_agent()}'
        self.verify = verify
        self.auth = auth

    @classmethod
    def is_code(cls, response: Response, status_name: str) -> bool:
        """
        Check whether the response has a status code that is consistent with
        a HTTP status name.
        """

        return response.status_code == requests.codes[status_name]

    @staticmethod
    def _get_user_agent() -> str:
        version = _gatherer_version
        version_path = Path('VERSION')
        if version_path.exists():
            with version_path.open('r', encoding='utf-8') as version_file:
                version = version_file.readline().rstrip()

        return f'{_gatherer_name}/{version}'
