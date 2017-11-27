"""
Jenkins build system source domain object.
"""

from .types import Source, Source_Types

@Source_Types.register('jenkins')
class Jenkins(Source):
    """
    Jenkins source.
    """

    @property
    def environment(self):
        return self.url

    @property
    def environment_url(self):
        return self.url

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
