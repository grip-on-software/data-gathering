"""
Module for collecting data from various versions of project definitions.

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

import json
import logging
from typing import Any, Dict, Optional, Type
from .base import Data, Definition_Parser, MetricNames, SourceUrl
from .data import Project_Definition_Data, Quality_Time_Data
from .metric import Metric_Difference
from .update import Update_Tracker
from ..domain import Project, Source
from ..domain.source.types import Source_Type_Error
from ..table import Table
from ..version_control.repo import PathLike, Version

class Collector:
    """
    Class that collects and aggregates data from different versions of project
    definition files.
    """

    def __init__(self, project: Project, source: Source,
                 repo_path: Optional[PathLike] = None,
                 target: str = 'project_definition', **options: Any):
        self._project = project
        self._update_tracker = Update_Tracker(self._project, source,
                                              target=target)
        self._options = options
        self._target = target
        if source.repository_class is not None:
            self._data: Data = Project_Definition_Data(project, source,
                                                       repo_path)
        else:
            self._data = Quality_Time_Data(project, source, repo_path)

    def collect(self, from_revision: Optional[Version] = None,
                to_revision: Optional[Version] = None) -> None:
        """
        Collect data from project definitions of revisions in the current range.
        """

        from_revision = self._update_tracker.get_start_revision(from_revision)
        versions = self._data.get_versions(from_revision, to_revision)
        end_revision = None
        data = None
        for index, version in enumerate(versions):
            logging.debug('Collecting version %s (%d in sequence)',
                          version['version_id'], index)
            data = self.collect_version(version)
            end_revision = version['version_id']

        self.finish(end_revision, self.use_update_data(data))

    def finish(self, end_revision: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        """
        Finish retrieving data based on the final version we collect.

        The `data` may contain additional data from this version to track
        between updates.
        """

        self._update_tracker.set_end(end_revision, data)

    def use_update_data(self, data: Optional[Dict[str, Any]]) \
            -> Optional[Dict[str, Any]]:
        # pylint: disable=no-self-use,unused-argument
        """
        Determine whether the provided data should be included in the update
        tracker.

        Collectors that make use of earlier data should return `data` or an
        alteration of it.
        """

        return None

    def collect_version(self, version: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Collect information from a version of the project definition,
        based on a dictionary containing details of a Subversion version.
        """

        try:
            parser = self.build_parser(version)
            contents = self._data.get_contents(version)
        except RuntimeError as error:
            logging.warning('Cannot create a parser for version %s: %s',
                            version['version_id'], str(error))
            return None

        try:
            parser.load_definition(self._data.filename, contents)
            result = parser.parse()
            self.aggregate_result(version, result)
            return result
        except RuntimeError as error:
            logging.warning("Problem with revision %s: %s",
                            version['version_id'], str(error))

        return None

    def collect_latest(self) -> None:
        """
        Collect information from the latest version of the project definition,
        and finalize the collection immediately.
        """

        latest_version = self._data.get_latest_version()
        data = self.collect_version(latest_version)
        self.finish(latest_version['version_id'], self.use_update_data(data))

    def aggregate_result(self, version: Dict[str, str], result: Dict[str, Any]) -> None:
        """
        Perform an action on the collected result to format it according to our
        needs.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def build_parser(self, version: Dict[str, str]) -> Definition_Parser:
        """
        Retrieve a project definition parser object that retrieves the data that
        we collect.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_parser_class(self) -> Type[Definition_Parser]:
        """
        Retrieve a parser class for the current collection target.
        """

        parsers = self._data.parsers
        if self._target not in parsers:
            raise RuntimeError(f'Could not find a parser for collection target {self._target}')

        return parsers[self._target]

class Project_Collector(Collector):
    """
    Collector that retrieves project information.
    """

    def __init__(self, project: Project, source: Source, **kwargs: Any):
        super().__init__(project, source, target='project_meta', **kwargs)
        self._meta: Dict[str, str] = {}

    def build_parser(self, version: Dict[str, str]) -> Definition_Parser:
        return self.get_parser_class()(**self._options)

    def aggregate_result(self, version: Dict[str, str], result: Dict[str, Any]) -> None:
        self._meta = result

    @property
    def meta(self) -> Dict[str, Any]:
        """
        Retrieve the parsed project metadata.
        """

        return self._meta

class Sources_Collector(Collector):
    """
    Collector that retrieves version control sources from project definitions.
    """

    def __init__(self, project: Project, source: Source, **kwargs: Any):
        super().__init__(project, source, target='project_sources', **kwargs)

        self._source_ids = Table('source_ids')
        self._parser_class = self.get_parser_class()

    def build_parser(self, version: Dict[str, str]) -> Definition_Parser:
        return self._parser_class(path=self._data.path, **self._options)

    def _build_metric_source(self, name: str, url: SourceUrl, source_type: str) -> None:
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

    def aggregate_result(self, version: Dict[str, str], result: Dict[str, Any]) -> None:
        sources_map = self._parser_class.SOURCES_MAP
        for name, metric_source in result.items():
            for metric_type, source_type in sources_map.items():
                # Loop over all known metric source class names and convert
                # them to our own Source objects.
                if metric_type in metric_source:
                    for url in metric_source[metric_type]:
                        self._build_metric_source(name, url, source_type)

    def finish(self, end_revision: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        super().finish(end_revision, data=data)

        self._source_ids.write(self._project.export_key)

class Metric_Options_Collector(Collector):
    """
    Collector that retrieves changes to metric targets from project definitions.
    """

    def __init__(self, project: Project, source: Source, **kwargs: Any):
        super().__init__(project, source, target='metric_options', **kwargs)
        self._source = source
        self._start: Optional[Version] = None
        self._diff = Metric_Difference(project,
                                       self._update_tracker.get_previous_data())

    def build_parser(self, version: Dict[str, str]) -> Definition_Parser:
        data_model = self._data.get_data_model(version)
        return self.get_parser_class()(file_time=version['commit_date'],
                                       data_model=data_model,
                                       **self._options)

    def collect(self, from_revision: Optional[Version] = None,
                to_revision: Optional[Version] = None) -> None:
        self._start = self._update_tracker.get_start_revision(from_revision)
        super().collect(from_revision, to_revision)

    def aggregate_result(self, version: Dict[str, str], result: Dict[str, Any]) -> None:
        for new_version, data in self._data.adjust_target_versions(version,
                                                                   result,
                                                                   self._start):
            self._diff.add_version(new_version, data)

    def finish(self, end_revision: Optional[Version],
               data: Optional[Dict[str, Any]] = None) -> None:
        if end_revision is None:
            logging.info('Metric options: No new revisions to parse')
        else:
            logging.info('Metric options: parsed up to revision %s',
                         end_revision)

        self._diff.export()
        if data is None:
            data = self._diff.previous_metric_targets

        metric_names: Dict[str, Optional[Dict[str, str]]] = {
            name: {
                'base_name': str(metric.get('base_name')),
                'domain_name': str(metric.get('domain_name')),
                'domain_type': str(metric.get('domain_type', ''))
            } if 'base_name' in metric else None
            for name, metric in data.items()
            if int(metric.get('number_of_sources', 1)) <= 1
        }
        metric_names_path = self._project.export_key / 'metric_names.json'
        if metric_names_path.exists():
            with metric_names_path.open('r', encoding='utf-8') as metric_names_file:
                existing_names: MetricNames = json.load(metric_names_file)
                if isinstance(existing_names, list):
                    existing_names = {
                        name: metric_names.get(name) for name in existing_names
                    }
                metric_names.update(existing_names)

        with metric_names_path.open('w', encoding='utf-8') as metric_names_file:
            json.dump(metric_names, metric_names_file)

        source = Source.from_type('metric_options',
                                  name=self._source.name,
                                  url=self._source.plain_url)
        if not self._project.sources.has_url(source.plain_url):
            self._project.sources.add(source)
            self._project.export_sources()

        super().finish(end_revision, data=data)

    def use_update_data(self, data: Optional[Dict[str, Any]]) \
            -> Optional[Dict[str, Any]]:
        return data
