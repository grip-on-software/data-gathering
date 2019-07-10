"""
SonarQube code quality inspection system source domain object.
"""

import logging
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from ...config import Configuration
from ...request import Session
from .types import Source, Source_Types

@Source_Types.register('sonar')
class Sonar(Source):
    """
    SonarQube source.
    """

    def __init__(self, *args, **kwargs):
        super(Sonar, self).__init__(*args, **kwargs)
        self._blacklisted = Configuration.is_url_blacklisted(self.url)

    @property
    def environment(self):
        return self.url

    @property
    def environment_url(self):
        return self.url

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')

    @property
    def version(self):
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
