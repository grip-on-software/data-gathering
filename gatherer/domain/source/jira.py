"""
Jira issue tracker source domain object.
"""

from .types import Source, Source_Types

@Source_Types.register('jira')
class Jira(Source):
    """
    Jira source.
    """

    @property
    def environment(self):
        return self.url

    @property
    def environment_url(self):
        return self.url
