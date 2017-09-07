"""
Quality reporting metrics history source domain object.
"""

from .types import Source, Source_Types

@Source_Types.register('history')
@Source_Types.register('compact-history')
class History(Source):
    """
    Metrics history source.
    """

    @property
    def environment(self):
        return self.url.split('/', 1)[0]

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
