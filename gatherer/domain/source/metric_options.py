"""
Quality reporting metric options source domain object.
"""

from .types import Source, Source_Types

@Source_Types.register('metric_options')
class Metric_Options(Source):
    """
    Metrics history source.
    """

    def _update_credentials(self):
        orig_parts, host = super(Metric_Options, self)._update_credentials()
        self._url = self._plain_url
        return orig_parts, host

    @property
    def environment(self):
        return ('metric_options', '/'.join(self.url.split('/')[:-1]))

    @property
    def environment_url(self):
        return self.url

    @property
    def file_name(self):
        """
        Retrieve the file name from the URL of the source.
        """

        return self.url.split('/')[-1]

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
