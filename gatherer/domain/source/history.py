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
        return ('metric_history', '/'.join(self.url.split('/')[:-1]))

    @property
    def environment_type(self) -> str:
        return "metric_history"

    @property
    def environment_url(self) -> Optional[str]:
        return '/'.join(self.url.split('/')[:-1])

    @property
    def file_name(self) -> Optional[str]:
        """
        Retrieve the file name from the "URL" of the source.

        If the file name cannot be extracted, then this is `None`.
        """

        part = self.url.split('/')[-1]
        if '.' not in part:
            return None

        return part

    @property
    def is_compact(self) -> bool:
        """
        Retrieve whether the history is in a compact format.
        """

        if self._type == 'compact-history':
            return True

        if self.file_name is not None:
            return self.file_name.startswith('compact-history.json')

        return False

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
