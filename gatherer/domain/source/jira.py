"""
Jira issue tracker source domain object.
"""

from __future__ import absolute_import
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

try:
    import urllib.parse
except ImportError:
    raise
from jira import JIRA
from .types import Source, Source_Types

@Source_Types.register('jira')
class Jira(Source):
    """
    Jira source.
    """

    def __init__(self, *args, **kwargs):
        self._username = kwargs.pop('username', None)
        self._password = kwargs.pop('password', None)
        self._jira_api = None

        super(Jira, self).__init__(*args, **kwargs)

    @property
    def environment(self):
        return self.plain_url.rstrip('/')

    @property
    def environment_url(self):
        return self.plain_url.rstrip('/')

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def jira_api(self):
        """
        Retrieve the JIRA API object for this source.
        """

        if self._jira_api is None:
            options = {
                "server": self.plain_url
            }

            parts = urllib.parse.urlsplit(self.url)
            if parts.username is not None:
                username = parts.username
                password = parts.password
            else:
                username = self._username
                password = self._password

            self._jira_api = JIRA(options, basic_auth=(username, password))

        return self._jira_api
