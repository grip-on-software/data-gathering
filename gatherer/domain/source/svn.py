"""
Subversion source domain object.
"""

import re
from . import Source, Source_Types
from ...svn import Subversion_Repository

@Source_Types.register('subversion')
class Subversion(Source):
    """
    Subversion source repository.
    """

    @property
    def repository_class(self):
        return Subversion_Repository

    def _update_credentials(self):
        orig_parts, host = super(Subversion, self)._update_credentials()

        # Remove trunk from the end of the URL
        self._url = re.sub(r'/(trunk/?)$', '', self._url)

        return orig_parts, host
