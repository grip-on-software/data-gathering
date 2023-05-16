"""
Subversion source domain object.

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
        orig_parts, host = super()._update_credentials()

        # Remove trunk from the end of the URL
        self._url = re.sub(r'/(trunk/?)$', '', self._url)

        return orig_parts, host

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
