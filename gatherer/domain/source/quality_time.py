"""
Quality Time domain object.
"""

from typing import Hashable, Optional
from .types import Source, Source_Types, Project

@Source_Types.register('quality-time')
class Quality_Time(Source):
    """
    Quality Time source.
    """

    @property
    def environment(self) -> Optional[Hashable]:
        return ('quality-time', self.url)

    @property
    def environment_url(self) -> Optional[str]:
        return self.url

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
