"""
Jenkins build system source domain object.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

try:
    import urllib.parse
except ImportError:
    raise
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
        return self.jenkins_api.version

    @property
    def jenkins_api(self):
        """
        Retrieve the Jenkins API object for this source.
        """

        if self._jenkins_api is None:
            parts = urllib.parse.urlsplit(self.url)
            unsafe = self.get_option('unsafe_hosts')
            self._jenkins_api = JenkinsAPI(self.plain_url,
                                           username=parts.username,
                                           password=parts.password,
                                           verify=unsafe is None)

        return self._jenkins_api
