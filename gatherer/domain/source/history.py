"""
Quality reporting metrics history source domain object.
"""

from typing import Hashable, Optional, Tuple
from urllib.parse import SplitResult
from .types import Source, Source_Types, Project

@Source_Types.register('history')
@Source_Types.register('compact-history')
@Source_Types.register('metric_history')
class History(Source):
    """
    Metrics history source.
    """

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super(History, self)._update_credentials()
        self._url = self._plain_url
        return orig_parts, host

    @property
    def environment(self) -> Optional[Hashable]:
        return ('metric_history', '/'.join(self.plain_url.split('/')[:-1]))

    @property
    def environment_type(self) -> str:
        return "metric_history"

    @property
    def environment_url(self) -> Optional[str]:
        return '/'.join(self.plain_url.split('/')[:-1])

    @property
    def file_name(self) -> Optional[str]:
        part = self.url.split('/')[-1]
        if '.' not in part:
            return None

        return part

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
