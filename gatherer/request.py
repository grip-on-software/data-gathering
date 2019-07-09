"""
Module that provides HTTP request sessions.
"""

from pathlib import Path
import requests
from . import __name__ as _gatherer_name, __version__ as _gatherer_version

class Session(requests.Session):
    """
    HTTP request session.

    This provides options to change verification and authentication settings
    for the session, and sets an appropriate user agent.
    """

    def __init__(self, verify=True, auth=None):
        super(Session, self).__init__()

        self.headers['User-Agent'] += ' ' + self._get_user_agent()
        self.verify = verify
        self.auth = auth

    @classmethod
    def is_code(cls, response, status_name):
        """
        Check whether the response has a status code that is consistent with
        a HTTP status name.
        """

        return response.status_code == requests.codes[status_name]

    @staticmethod
    def _get_user_agent():
        version_path = Path('VERSION')
        if version_path.exists():
            with version_path.open('r') as version_file:
                version = version_file.readline().rstrip()
        else:
            version = _gatherer_version

        return '{}/{}'.format(_gatherer_name, version)
