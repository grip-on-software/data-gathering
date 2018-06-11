"""
Quality reporting metrics history source domain object.
"""

from .types import Source, Source_Types

@Source_Types.register('history')
@Source_Types.register('compact-history')
@Source_Types.register('metric_history')
class History(Source):
    """
    Metrics history source.
    """

    def _update_credentials(self):
        orig_parts, host = super(History, self)._update_credentials()
        self._url = self._plain_url
        return orig_parts, host

    @property
    def environment(self):
        return '/'.join(self.url.split('/')[:-1])

    @property
    def environment_type(self):
        return "metric_history"

    @property
    def environment_url(self):
        return '/'.join(self.url.split('/')[:-1])

    @property
    def file_name(self):
        """
        Retrieve the file name from the "URL" of the source.
        """

        return self.url.split('/')[-1]

    @property
    def is_compact(self):
        """
        Retrieve whether the history is in a compact format.
        """

        return self._type == 'compact-history'

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
