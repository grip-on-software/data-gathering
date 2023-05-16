"""
Module defining base types for parsing project definitions.

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
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, Union
from ..version_control.repo import Version

MetricNames = Union[List[str], Dict[str, Optional[Dict[str, str]]]]
SourceUrl = Optional[Union[str, Tuple[str, str, str]]]
UUID = re.compile('^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

class Definition_Parser:
    """
    Base class to describe a parser that is able to understand a definition
    of a project within a quality reporting system.
    """

    SOURCES_MAP: Dict[str, str] = {}
    SOURCES_DOMAIN_FILTER: List[str] = []

    def __init__(self, **options: Any) -> None:
        pass

    def load_definition(self, filename: str, contents: Union[str, bytes]) -> None:
        """
        Load the contents of a project definition.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def parse(self) -> Dict[str, Any]:
        """
        Parse the definition to obtain a dictionary of properties obtained
        from the report, such as project metadata, metrics and their targets
        and/or sources.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Data:
    """
    Abstract base class for a data source of the project definition.
    """

    def get_versions(self, from_revision: Optional[Version],
                     to_revision: Optional[Version]) -> Iterable[Dict[str, str]]:
        """
        Receive an iterable of dictionaries containing version metadata for the
        versions that we can retrieve for the project definition.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_latest_version(self) -> Dict[str, str]:
        """
        Retrieve the version metadata of the latest version.

        At least the 'version_id' is provided.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_contents(self, version: Dict[str, str]) -> Union[str, bytes]:
        """
        Retrieve the contents of a project definition based on the version
        metadata for that version of the definition.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_data_model(self, version: Dict[str, str]) -> Dict[str, Any]:
        """
        Receive the project definition's data model.

        If the data source has no data model, then an empty dictionary is
        returned.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def adjust_target_versions(self, version: Dict[str, str],
                               result: Dict[str, Any],
                               start_version: Optional[Version]) \
            -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
        """
        Update metric target version information to enrich with more
        intermediate versions and to limit the result to only contain updates
        since the start version.

        Returns a list, sorted ascendingly by version, of new version
        dictionaries and result dictionaries, without any changes from
        `start_version` or earlier. If no adjustments are necessary, such
        as when parsing only one version, or if all version and metric data wa
        available during the parse, then return `[(version, result)]`.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def path(self) -> str:
        """
        A path that contains information relevant for the project definition.
        """

        return "."

    @property
    def filename(self) -> str:
        """
        A filename that distinguishes the project definition data source.
        This name can be used within logging, for example.
        """

        return "project_definition"

    @property
    def parsers(self) -> Dict[str, Type[Definition_Parser]]:
        """
        Retrieve a dictionary of definition parsers that are available for
        the project definition format.
        """

        return {}
