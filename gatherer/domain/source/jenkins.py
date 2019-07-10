"""
Jenkins build system source domain object.
"""

import urllib.parse
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from ...config import Configuration
from ...jenkins import Jenkins as JenkinsAPI
from .types import Source, Source_Types

@Source_Types.register('jenkins')
class Jenkins(Source):
    """
    Jenkins source.
    """

    def __init__(self, *args, **kwargs):
        super(Jenkins, self).__init__(*args, **kwargs)
        self._jenkins_api = None

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
        try:
            self.jenkins_api.timeout = 3
            return self.jenkins_api.version
        except (RuntimeError, ConnectError, HTTPError, Timeout):
            return ''
        finally:
            if self._jenkins_api is not None:
                self.jenkins_api.timeout = None

    @property
    def jenkins_api(self):
        """
        Retrieve the Jenkins API object for this source.
        """

        if Configuration.is_url_blacklisted(self.url):
            raise RuntimeError('Jenkins API for {} is blacklisted'.format(self.plain_url))

        if self._jenkins_api is None:
            parts = urllib.parse.urlsplit(self.url)
            unsafe = self.get_option('unsafe_hosts')
            self._jenkins_api = JenkinsAPI(self.plain_url,
                                           username=parts.username,
                                           password=parts.password,
                                           verify=unsafe is None)

        return self._jenkins_api
