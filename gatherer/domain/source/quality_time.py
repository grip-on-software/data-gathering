"""
Quality Time domain object.

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

from typing import Hashable, Optional, Type
from .types import Source, Source_Types, Project
from ...project_definition.data import Quality_Time_Data

@Source_Types.register('quality-time')
class Quality_Time(Source):
    """
    Quality Time source.
    """

    @property
    def project_definition_class(self) -> Type[Quality_Time_Data]:
        return Quality_Time_Data

    @property
    def environment(self) -> Optional[Hashable]:
        return ('quality-time', self.plain_url)

    @property
    def environment_url(self) -> Optional[str]:
        return self.plain_url

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
        raise RuntimeError('Source does not support updating SSH key')
