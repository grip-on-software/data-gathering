"""
Module defining base types for parsing project definitions.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from abc import ABCMeta
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union, \
    TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from ..config import Configuration
from ..table import Row
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
else:
    Project = object
    Source = object

DataUrl = Optional[Union[str, Dict[str, str]]]

MetricNameData = Optional[Dict[str, str]]
MetricNames = Dict[str, MetricNameData]
MetricTargets = Dict[str, Row]
SourceUrl = Optional[Union[str, Tuple[str, str, str]]]

# Version identifier and metadata
Revision = Union[int, str]
Version = Dict[str, str]

UUID = re.compile('^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

class Parser(metaclass=ABCMeta):
    """
    Base class to describe a parser that post-processes result data from the
    project definition source.
    """

    SOURCES_MAP: Dict[str, str] = {}
    SOURCES_DOMAIN_FILTER: List[str] = []

    def __init__(self, version: Optional[Version] = None) -> None:
        self._version = version

    @property
    def version(self) -> Optional[Version]:
        """
        Retrieve the version for which this parser is active.
        """

        return self._version

    def parse(self) -> Dict[str, Any]:
        """
        Parse the definition or other data from the source to obtain a
        dictionary of properties obtained for a type of entity, such as project
        metadata, metrics and their targets and/or sources.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Definition_Parser(Parser):
    """
    Base class to describe a parser that is able to understand a definition
    of a project.
    """

    def load_definition(self, filename: str, contents: Dict[str, Any]) -> None:
        """
        Load the contents of a project definition.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Measurement_Parser(Parser, metaclass=ABCMeta):
    """
    Parser that is able to use intermediate measurement data.
    """

    def __init__(self, metrics: Optional[MetricNames] = None,
                 measurements: Optional[List[Dict[str, Any]]] = None,
                 version: Optional[Version] = None):
        super().__init__(version=version)
        if metrics is not None:
            self._metrics = metrics
        else:
            self._metrics = {}

        self._measurements = measurements

class Metric_Parser(Parser, metaclass=ABCMeta):
    """
    Parser that is able to use a project definition data model for translating
    metrics into relevant metadata.
    """

    def __init__(self, data_model: Optional[Dict[str, Any]] = None,
                 version: Optional[Version] = None) -> None:
        super().__init__(version=version)
        if data_model is None:
            self._data_model: Dict[str, Any] = {}
        else:
            self._data_model = data_model

class Data:
    """
    Abstract base class for a data source of the project definition.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        self._project = project

        self._query: Dict[str, str] = {}
        if isinstance(url, dict):
            self._query = url.copy()
            url = None

        if url is None:
            self._url = source.plain_url
        else:
            self._url = url

        if Configuration.is_url_blacklisted(self._url):
            raise RuntimeError(f'Cannot use blacklisted URL as a definitions source: {self._url}')

    def get_url(self, path: str = '', query: DataUrl = None) -> str:
        """
        Format an URL for the source.

        This may be useful for data sources using the project definition from
        the remote source, for example via a web API. The `path` should be a
        path to the API route, relative to the host of the source. The `query`
        is additional query string parameters for the API route, either in
        string or key-value dictionary form.
        """

        parts = urlsplit(self._url)
        if path == '':
            path = parts.path

        if query is None:
            extra_query: Dict[str, str] = {}
        elif not isinstance(query, dict):
            # Always take the last in the query
            extra_query = dict(parse_qsl(query))
        else:
            extra_query = query

        # Combine with predetermined query, preferring the parameter
        final_query = self._query.copy()
        final_query.update(extra_query)

        final_parts = (parts.scheme, parts.hostname, path,
                       urlencode(final_query), '')
        return urlunsplit(final_parts)

    def get_versions(self, from_revision: Optional[Revision],
                     to_revision: Optional[Revision]) -> Sequence[Version]:
        """
        Receive a sequence of dictionaries containing version metadata for the
        versions that we can retrieve for the project definition. Only versions
        between the `from_revision` and `to_revision`, which identify the
        versions, are provided. If the project definition source does not have
        a concept of versioning for the relevant entities, then this may
        return a 1-item list of the latest version.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_start_version(self) -> Optional[Version]:
        """
        Retrieve the version metadata to use to start collecting data from, if
        no other version is known.

        This should be overridden with a valid version, even though other data
        retrieval methods accept missing start versions.
        """

        return None

    def get_latest_version(self) -> Version:
        """
        Retrieve the version metadata of the latest version.

        At least the 'version_id' is provided.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_contents(self, version: Version) -> Dict[str, Any]:
        """
        Retrieve the contents of a project definition based on the `version`
        metadata for that version of the definition. This is then usable as
        the basis for parsing various information from the definition, although
        parser may themselves collect more information if necessary.

        If the project definition is not versioned, then the definition is
        returned without regard of the `version` parameter. If the definition
        could not be retrieved, then a `RuntimeError` is raised.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_data_model(self, version: Version) -> Dict[str, Any]:
        """
        Receive the project definition's data model.

        The data model should at least contain information regarding metrics
        that are measured for the project, in particular their default values.
        It may also describe sources of the project and metadata.

        The `version` provides metadata for the version of the data model to
        retrieve. If the data model is not linked to a version because it
        lacks versioning, then the project definition data source ignores the
        parameter.

        If the data source has no data model, then an empty dictionary is
        returned. If the data source does use data models but the data model
        could not be retrieved, then a `RuntimeError` is raised.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def update_source_definitions(self, contents: Dict[str, Any]) -> None:
        """
        Update a project definition `contents` to enrich it with more details
        on sources.

        This method alters the `contents`. If no further details can be added,
        then subclasses can leave the implementation empty.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def adjust_target_versions(self, version: Version, result: Dict[str, Any],
                               from_revision: Optional[Revision] = None) \
            -> List[Tuple[Version, MetricTargets]]:
        """
        Update metric target version information to enrich with more details and
        intermediate versions and to limit the result to only contain updates
        since the start version.

        Returns a list, sorted ascendingly by version, of new version metadata
        dictionaries and result dictionaries, without any changes from
        `from_revision` or earlier. If no adjustments are necessary, such
        as when parsing only one version, or if all version and metric data was
        available during the parse, i.e., the project definition source does not
        have versioning of metric targets, then return `[(version, result)]`,
        assuming that `result` is formatted as a dictionary with unique metric
        IDs as keys and metric data as values. If the adjustments could not be
        made, then a `RuntimeError` is raised.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def get_measurements(self, metrics: Optional[MetricNames], version: Version,
                         from_revision: Optional[Revision] = None) -> List[Row]:
        """
        Retrieve the measurements for any quality metrics measured at the
        project definition, with `metrics` providing a candidate list of metric
        name data fields with identifiers as kets. This only collects
        measurements up to a certain date determined by the `version` and
        optionally starting from a `start_version` if this is supported by the
        project definition data.

        The project definition data source may retrieve more metrics than those
        mentioned in the metric names, or also exclude predefined metric names,
        based on data collection needs. If `metrics` is not provided but
        necessary to retrieve measurements, then a `RuntimeError` is raised.

        Returns a list of measurement data for all of the retrieved metrics
        combined, providing dictionaries with measurements in a standard format.
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
    def parsers(self) -> Dict[str, Type[Parser]]:
        """
        Retrieve a dictionary of definition parsers that are available for
        the project definition format.
        """

        return {}
