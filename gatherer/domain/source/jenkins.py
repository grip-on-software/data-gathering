"""
Jenkins build system source domain object.
"""

from typing import Hashable, Optional
from urllib.parse import urlsplit
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from ...config import Configuration
from ...jenkins import Jenkins as JenkinsAPI
from .types import Source, Source_Types, Project

@Source_Types.register('jenkins')
class Jenkins(Source):
    """
    Jenkins source.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)
        self._jenkins_api: Optional[JenkinsAPI] = None

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
        try:
            self.jenkins_api.timeout = 3
            return self.jenkins_api.version
        except (RuntimeError, ConnectError, HTTPError, Timeout):
            return ''
        finally:
            if self._jenkins_api is not None:
                self.jenkins_api.timeout = None

    @property
    def jenkins_api(self) -> JenkinsAPI:
        """
        Retrieve the Jenkins API object for this source.
        """

        if Configuration.is_url_blacklisted(self.url):
            raise RuntimeError('Jenkins API for {} is blacklisted'.format(self.plain_url))

        if self._jenkins_api is None:
            parts = urlsplit(self.url)
            unsafe = self.get_option('unsafe_hosts')
            self._jenkins_api = JenkinsAPI(self.plain_url,
                                           username=parts.username,
                                           password=parts.password,
                                           verify=unsafe is None)

        return self._jenkins_api
