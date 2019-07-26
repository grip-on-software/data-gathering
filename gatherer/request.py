"""
Module that provides HTTP request sessions.
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

        self.headers['User-Agent'] += ' ' + self._get_user_agent()
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
            with version_path.open('r') as version_file:
                version = version_file.readline().rstrip()

        return f'{_gatherer_name}/{version}'
