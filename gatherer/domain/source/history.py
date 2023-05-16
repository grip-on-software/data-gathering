"""
Quality reporting metrics history source domain object.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
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
        orig_parts, host = super()._update_credentials()
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
