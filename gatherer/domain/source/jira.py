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
        return self.url.rstrip('/')

    @property
    def environment_url(self):
        return self.url.rstrip('/')

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
