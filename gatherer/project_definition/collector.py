"""
Module for collecting data from various versions of project definitions and
related quality metric data.

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
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from .base import DataUrl, MetricNames, SourceUrl, Revision, Version
from .metric import Metric_Difference
from .base import Parser, Definition_Parser, Measurement_Parser, Metric_Parser
from .update import Update_Tracker
from ..domain import Project, Source
from ..domain.source.types import Source_Type_Error
from ..table import Table, Row

class Collector(metaclass=ABCMeta):
    """
    Base class to describe the collection process of data from the project
    definition source, possibly regarding data not related to the definition
    itself, but to metrics and measurements of the project artifacts.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        self._project = project
        self._update_tracker = Update_Tracker(self._project, source,
                                              target=self.target)

        project_definition_class = source.project_definition_class
        if project_definition_class is None:
            raise TypeError('Source does not have a project defitinion class')

        self._data = project_definition_class(project, source, url)

    @property
    def target(self) -> str:
        """
        Retrieve the type of the collector, which is used to uniquely
        identify the update tracker for the collected data.
        """

        raise NotImplementedError('Subclass must designate collector type')

    def collect(self, from_revision: Optional[Revision] = None,
                to_revision: Optional[Revision] = None) -> None:
        """
        Collect data from the project definition source relevant to the current
        collector, possibly from a versioned system by selecting version between
        specific ranges identified by the `from_revision` and `to_revision`,
        which could correspond with version control system revision numbers,
        commit hashes or timestamps, depending on the source. If the source
        does not support versioning for the data, then the revisions may be
        ignored. If `from_revision` is not given, then the update tracker may
        provide the starting revision or it defaults to the first version. If
        `to_revision` is not given, then it is considered to be the last version
        at the source data.
        """

        raise NotImplementedError('Subclasses must implement this method')

    def collect_version(self, version: Version) -> Optional[Dict[str, Any]]:
        """
        Collect data from the project definition source relevant to the current
        collector based on a `version`, which is a dictionary containing
        metadata of a version. If the source does not support versioning for the
        data, then the `version` is ignored.

        Returns the collected data, or `None` if it is already handled, for
        example by being stored in a table.
        """

        raise NotImplementedError('Subclasses must implement this method')

    def collect_latest(self) -> None:
        """
        Collect data from the latest version of the project definition.
        """

        latest_version = self._data.get_latest_version()
        data = self.collect_version(latest_version)
        self.finish(latest_version, data)

    @property
    def use_update_data(self) -> bool:
        """
        Determine whether the provided data should be included in the update
        tracker.

        Collectors that make use of earlier data return `True` to store the
        latest version's data in the update tracker.
        """

        return False

    def finish(self, version: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        """
        Finish retrieving data based on the final version we collect.

        The `data` may contain additional data from this version to track
        between updates.
        """

        if version is not None:
            revision: Optional[Revision] = version['version_id']
        else:
            revision = None
        self._update_tracker.set_end(revision,
                                     data if self.use_update_data else None)

    def build_parser(self, version: Version) -> Parser:
        """
        Retrieve a project definition parser object that retrieves the data that
        we collect. The parser may be provided the `version` for collecting
        additional version-specific data, or other details from the collector.
        """

        parser = self.get_parser_class()
        return parser(version=version)

    def get_parser_class(self) -> Type[Parser]:
        """
        Retrieve a parser class for the current collection target.
        """

        parsers = self._data.parsers
        target = self.target
        if target not in parsers:
            raise RuntimeError(f'Could not find a parser for collection target {target}')

        return parsers[target]

class Metric_Collector(Collector, metaclass=ABCMeta):
    """
    Collector for metric information which makes use of the project definition's
    data model during the parsing of the collected data.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None,
                 data_model: Optional[Dict[str, Any]] = None):
        super().__init__(project, source, url=url)
        self._data_model = data_model

    @property
    def data_model(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the cached data model provided to the collector or retrieved
        when building the parser.

        If the data model has not been loaded, then `None` is returned.
        """

        return self._data_model

    def build_parser(self, version: Version) -> Parser:
        parser = self.get_parser_class()
        if not issubclass(parser, Metric_Parser):
            raise TypeError('Parser is not a metric parser')

        if self._data_model is None:
            self._data_model = self._data.get_data_model(version)
        return parser(data_model=self._data_model, version=version)

class Definition_Collector(Collector, metaclass=ABCMeta):
    """
    Class that collects and aggregates data from different versions of project
    definition files.
    """

    def collect(self, from_revision: Optional[Revision] = None,
                to_revision: Optional[Revision] = None) -> None:
        """
        Collect data from project definitions of revisions in the current range.
        """

        from_revision = self._update_tracker.get_start_revision(from_revision)
        versions = self._data.get_versions(from_revision, to_revision)
        version = None
        for index, version in enumerate(versions):
            logging.debug('Collecting version %s (%d in sequence)',
                          version['version_id'], index)
            self.collect_version(version)

        self.finish(version)

    def collect_version(self, version: Version) -> None:
        """
        Collect information from a `version` of the project definition,
        based on a dictionary containing metadata of a version.
        """

        try:
            contents = self.get_data(version)
            parser = self.build_parser(version)
        except RuntimeError as error:
            logging.warning('Cannot create a parser for version %s: %s',
                            version['version_id'], str(error))
            return

        try:
            if isinstance(parser, Definition_Parser):
                parser.load_definition(self._data.filename, contents)
            result = parser.parse()
            self.aggregate_result(version, result)
        except RuntimeError as error:
            logging.warning("Problem with revision %s: %s",
                            version['version_id'], str(error))

    def get_data(self, version: Version) -> Dict[str, Any]:
        """
        Retrieve the unprocessed source data for the `version`, which is the
        project definition. Subclasses may update the returned data before
        it is loaded into to the parser.
        """

        return self._data.get_contents(version)

    def aggregate_result(self, version: Version, result: Dict[str, Any]) -> None:
        """
        Perform an action on the collected result to format it according to our
        needs.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class Project_Collector(Definition_Collector):
    """
    Collector that retrieves project information.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url=url)
        self._meta: Dict[str, str] = {}

    @property
    def target(self) -> str:
        return 'project_meta'

    def aggregate_result(self, version: Version, result: Dict[str, Any]) -> None:
        self._meta = result

    @property
    def meta(self) -> Dict[str, str]:
        """
        Retrieve the parsed project metadata.
        """

        return self._meta

class Sources_Collector(Definition_Collector):
    """
    Collector that retrieves version control sources from project definitions.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url=url)

        self._source_ids = Table('source_ids', merge_update=True)
        self._parser_class = self.get_parser_class()
        # Data aggregated from latest version
        self._result: Dict[str, Any] = {}

    @property
    def target(self) -> str:
        return 'project_sources'

    def _build_metric_source(self, name: str, url: SourceUrl, source_type: str) -> None:
        if url is None:
            return

        try:
            if isinstance(url, tuple):
                domain_type = url[2]
                source_id = url[1]
                url = url[0]
                source = Source.from_type(source_type, name=name, url=url)
                self._source_ids.append({
                    "domain_name": name,
                    "url": url,
                    "source_id": source_id,
                    "source_type": source.environment_type,
                    "domain_type": domain_type
                })
                # Do not add sources belonging to search domain types to the
                # main sources list, such as a VCS in a document object.
                if domain_type in self._parser_class.SOURCES_DOMAIN_FILTER:
                    return
            else:
                source = Source.from_type(source_type, name=name, url=url)

            if not self._project.has_source(source):
                self._project.sources.add(source)
        except Source_Type_Error:
            logging.exception('Could not register source')

    def get_data(self, version: Version) -> Dict[str, Any]:
        contents = super().get_data(version)
        self._data.update_source_definitions(contents)
        return contents

    def aggregate_result(self, version: Version, result: Dict[str, Any]) -> None:
        sources_map = self._parser_class.SOURCES_MAP
        for name, metric_source in result.items():
            for metric_type, source_type in sources_map.items():
                # Loop over all known metric source class names and convert
                # them to our own Source objects.
                if metric_type in metric_source:
                    for url in metric_source[metric_type]:
                        self._build_metric_source(name, url, source_type)

        self._result = result

    def finish(self, version: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        super().finish(version, data=data if data is not None else self._result)

        self._source_ids.write(self._project.export_key)

class Unversioned_Collector(Collector, metaclass=ABCMeta):
    """
    Collector where only the latest version is able to be collected.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url=url)
        self._start: Optional[Revision] = None
        self._table = Table(self.table_name, merge_update=True)
        # Unprocessed intermediate data to be passed to the parser
        self._intermediate: List[Dict[str, Any]] = []

    @property
    def table_name(self) -> str:
        """
        Table to store aggregated results in.
        """

        raise NotImplementedError('Must be defined by subclasses')

    def collect(self, from_revision: Optional[Revision] = None,
                to_revision: Optional[Revision] = None) -> None:
        from_revision = self._update_tracker.get_start_revision(from_revision)
        if from_revision is not None:
            self._start = from_revision
        else:
            start_version = self._data.get_start_version()
            if start_version is not None:
                self._start = start_version['version_id']

        version = self._data.get_versions(from_revision, to_revision)[-1]
        self.collect_version(version)

        self.finish(version)

    def collect_version(self, version: Version) -> None:
        data = self.get_data(version)
        self.aggregate_result(version, data)

    def get_data(self, version: Version) -> List[Row]:
        """
        Retrieve aggregate data from the data source relevant to the collector.
        The `version` is the most recent version at the project definition
        data source based on the `from_revision` and `to_revision` range.
        The returned value is table-like data about entities in their state as
        found in the version (or their current state). This is then usable as
        additional parameters to the parser.
        """

        raise NotImplementedError('Must be defined by subclasses')

    def aggregate_result(self, version: Version, data: List[Dict[str, Any]]) -> None:
        """
        Post-process the collected result to format it according to the table.
        """

        self._intermediate = data
        parser = self.build_parser(version)
        result = parser.parse()
        self._table.extend(result[version['version_id']])

    def finish(self, version: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        super().finish(version, data=data)
        self._table.write(self._project.export_key)

class Measurements_Collector(Unversioned_Collector):
    """
    Collector that retrieves measurements of metrics defined for the project at
    the project definition source.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url=url)
        self._source = source
        self._metrics = self._read_metric_names()

    @property
    def target(self) -> str:
        return 'measurements'

    @property
    def table_name(self) -> str:
        return 'metrics'

    def _read_metric_names(self) -> Optional[MetricNames]:
        metric_path = Path(self._project.export_key, 'metric_names.json')
        if not metric_path.exists():
            logging.warning('No metric names available for %s',
                            self._project.key)
            return None

        with metric_path.open('r', encoding='utf-8') as metric_file:
            return json.load(metric_file)

    def build_parser(self, version: Version) -> Parser:
        parser = self.get_parser_class()
        if not issubclass(parser, Measurement_Parser):
            raise TypeError('Parser is not a measurement parser')

        return parser(metrics=self._metrics, measurements=self._intermediate,
                      version=version)

    def collect_version(self, version: Version) -> None:
        if self._start is None and self._source.type == 'quality-time':
            # Check if old update tracker exists and read start date from there
            legacy_date_path = Path(self._project.export_key,
                                    'quality_time_measurement_date.txt')
            if legacy_date_path.exists():
                with legacy_date_path.open('r', encoding='utf-8') as date_file:
                    self._start = date_file.read()

        super().collect_version(version)

    def get_data(self, version: Version) -> List[Row]:
        return self._data.get_measurements(self._metrics, version,
                                           from_revision=self._start)

class Metric_Defaults_Collector(Metric_Collector, Unversioned_Collector):
    """
    Collector that retrieves default targets for metrics from the source.
    """

    @property
    def target(self) -> str:
        return 'metric_defaults'

    @property
    def table_name(self) -> str:
        return 'metric_defaults'

    def get_data(self, version: Version) -> List[Row]:
        return []

class Metric_Options_Collector(Metric_Collector, Definition_Collector):
    """
    Collector that retrieves changes to metric targets from project definitions.
    """

    def __init__(self, project: Project, source: Source, url: DataUrl = None,
                 data_model: Optional[Dict[str, Any]] = None):
        super().__init__(project, source, url=url, data_model=data_model)
        self._source = source
        self._start: Optional[Revision] = None
        self._metric_names: Dict[str, Any] = {}
        self._diff = Metric_Difference(project,
                                       self._update_tracker.get_previous_data())

    @property
    def target(self) -> str:
        return 'metric_options'

    def collect(self, from_revision: Optional[Revision] = None,
                to_revision: Optional[Revision] = None) -> None:
        self._start = self._update_tracker.get_start_revision(from_revision)
        super().collect(from_revision, to_revision)

    def aggregate_result(self, version: Version, result: Dict[str, Any]) -> None:
        self._metric_names.update(result)
        for new_version, data in self._data.adjust_target_versions(version,
                                                                   result,
                                                                   self._start):
            self._diff.add_version(new_version, data)

    def finish(self, version: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        if version is None:
            logging.info('Metric options: No new revisions to parse')
        else:
            logging.info('Metric options: parsed up to revision %s',
                         version['version_id'])

        self._diff.export()

        metric_names: MetricNames = {
            name: {
                'base_name': str(metric.get('base_name')),
                'domain_name': str(metric.get('domain_name')),
                'domain_type': str(metric.get('domain_type', '')),
                'scale': str(metric.get('scale', 'count'))
            } if 'base_name' in metric else None
            for name, metric in self._metric_names.items()
        }
        metric_names_path = Path(self._project.export_key, 'metric_names.json')
        if metric_names_path.exists():
            with metric_names_path.open('r',
                                        encoding='utf-8') as metric_names_file:
                existing_names: MetricNames = json.load(metric_names_file)
                existing_names.update(metric_names)
                metric_names = existing_names

        try:
            with metric_names_path.open('w',
                                        encoding='utf-8') as metric_names_file:
                json.dump(metric_names, metric_names_file)
        except FileNotFoundError:
            logging.exception('Could not write metric names for %s',
                              self._project.key)

        super().finish(version,
                       data=data if data is not None else self._diff.previous_metric_targets)

    @property
    def use_update_data(self) -> bool:
        return True
