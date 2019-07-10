"""
Jira issue tracker source domain object.
"""

import urllib.parse
from jira import JIRA
from jira.exceptions import JIRAError
from .types import Source, Source_Types
from ...config import Configuration

@Source_Types.register('jira')
class Jira(Source):
    """
    Jira source.
    """

    def __init__(self, *args, **kwargs):
        self._username = kwargs.pop('username', None)
        self._password = kwargs.pop('password', None)
        self._agile_path = JIRA.DEFAULT_OPTIONS["agile_rest_path"]
        self._jira_api = None
        self._version = None

        super(Jira, self).__init__(*args, **kwargs)

    def _update_credentials(self):
        orig_parts, host = super(Jira, self)._update_credentials()
        if self.has_option(host, 'agile_rest_path'):
            self._agile_path = self._credentials.get(host, 'agile_rest_path')

        return orig_parts, host

    @property
    def environment(self):
        return self.plain_url.rstrip('/')

    @property
    def environment_url(self):
        return self.plain_url.rstrip('/')

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def version(self):
        if self._version is None:
            try:
                self._version = self.jira_api.server_info()['version']
            except (RuntimeError, JIRAError, KeyError):
                self._version = ''

        return self._version

    @property
    def jira_agile_path(self):
        """
        Retrieve the REST path to use for JIRA Agile requests.
        """

        return self._agile_path

    @property
    def jira_api(self):
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

            parts = urllib.parse.urlsplit(self.url)
            if parts.username is not None:
                auth = (parts.username, parts.password)
            elif self._username is not None:
                auth = (self._username, self._password)
            else:
                auth = None

            self._jira_api = JIRA(options, basic_auth=auth, max_retries=0)

        return self._jira_api
