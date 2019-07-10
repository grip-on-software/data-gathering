"""
Subversion source domain object.
"""

import re
from typing import Tuple, Type
from urllib.parse import SplitResult
from .types import Source, Source_Types, Project
from ...svn import Subversion_Repository

@Source_Types.register('subversion')
class Subversion(Source):
    """
    Subversion source repository.
    """

    SSH_PROTOCOL = 'svn+ssh'

    @property
    def repository_class(self) -> Type[Subversion_Repository]:
        return Subversion_Repository

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super(Subversion, self)._update_credentials()

        # Remove trunk from the end of the URL
        self._url = re.sub(r'/(trunk/?)$', '', self._url)

        return orig_parts, host

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
