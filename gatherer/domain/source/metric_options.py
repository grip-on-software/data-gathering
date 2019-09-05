"""
Quality reporting metric options source domain object.
"""

from typing import Hashable, Optional, Tuple
from urllib.parse import SplitResult
from .types import Source, Source_Types, Project

@Source_Types.register('metric_options')
class Metric_Options(Source):
    """
    Metrics history source.
    """

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        orig_parts, host = super(Metric_Options, self)._update_credentials()
        self._url = self._plain_url
        return orig_parts, host

    @property
    def environment(self) -> Optional[Hashable]:
        return ('metric_options', '/'.join(self.plain_url.split('/')[:-1]))

    @property
    def environment_url(self) -> Optional[str]:
        return self.plain_url

    @property
    def file_name(self) -> str:
        """
        Retrieve the file name from the URL of the source.
        """

        return self.url.split('/')[-1]

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
