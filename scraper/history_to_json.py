"""
Script to obtain a metrics history file and convert it to a JSON format
readable by the database importer.

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

from argparse import ArgumentParser, Namespace
from datetime import datetime
import gzip
import io
import json
import logging
import os
from pathlib import Path
from types import TracebackType
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Type, \
    Union, TYPE_CHECKING
from gatherer.domain import Project, Source
from gatherer.domain.source import Quality_Time
from gatherer.log import Log_Setup
from gatherer.project_definition.base import MetricNames, UUID
from gatherer.project_definition.data import Quality_Time_Data
from gatherer.utils import get_utc_datetime, parse_date

MetricRow = Dict[str, Union[str, Tuple[str, str, str]]]
OpenFile = Union[io.FileIO, gzip.GzipFile]
IOLike = Union[OpenFile, io.StringIO]
if TYPE_CHECKING:
    # pylint: disable=unsubscriptable-object
    PathLike = Union[str, os.PathLike[str]]
else:
    PathLike = os.PathLike

Parts = Union[str, None, Tuple[Optional[Path], Optional[str]], Tuple[str, ...]]
Transform = Callable[[Project, Namespace], Parts]
Generate = Callable[[Union[Parts, str], Set[Source], List['Location'],
                     str, str], Optional['Data_Source']]

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain metrics history from Quality-time and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def read_quality_time_measurements(project: Project, source: Source,
                                   url: Optional[str] = None,
                                   start_date: str = "1900-01-01 00:00:00") \
        -> Tuple[List[Dict[str, str]], str]:
    """
    Read metric data from a quality time project definition report.
    """

    metric_data: List[Dict[str, str]] = []
    metric_path = project.export_key / 'metric_names.json'
    if not metric_path.exists():
        logging.warning('No metric names available for %s', project.key)
        return metric_data, start_date

    data = Quality_Time_Data(project, source, url)
    with metric_path.open('r', encoding='utf-8') as metric_file:
        metrics: MetricNames = json.load(metric_file)

    cutoff_date = get_utc_datetime(start_date.strip())
    version = data.get_latest_version()
    for metric_uuid in metrics:
        if not UUID.match(metric_uuid):
            continue

        metric_data.extend(fetch_quality_time_measurements(data, metric_uuid,
                                                           version,
                                                           cutoff_date,
                                                           metrics))

    return metric_data, version['version_id']

def fetch_quality_time_measurements(data: Quality_Time_Data, metric_uuid: str,
                                    version: Dict[str, str],
                                    cutoff_date: datetime,
                                    metrics: MetricNames) \
        -> List[Dict[str, str]]:
    """
    Retrieve the measurements of a Quality Time metric from its source.
    """

    metric_data: List[Dict[str, str]] = []
    for measurement in data.get_measurements(metric_uuid, version,
                                             cutoff_date=cutoff_date):
        if isinstance(metrics, dict):
            metric = metrics[metric_uuid]
            if isinstance(metric, dict):
                measurement.update(metric)

        metric_data.append(measurement)

    return metric_data

class Location:
    """
    Location of a history file.
    """

    COMPACT_HISTORY_FILENAME = 'compact-history.json'

    def __init__(self, parts: Union[str, Tuple[str, ...]]) -> None:
        if isinstance(parts, str):
            parts = (str(parts),)

        self._parts = tuple(parts)
        self._location = "/".join(parts)

    @property
    def parts(self) -> Tuple[str, ...]:
        """
        Retrieve the parts of the path or URL that were used to find the
        location of the history file.
        """

        return self._parts

    @property
    def location(self) -> str:
        """
        Retrieve the path or URL to the history file.
        """

        return self._location

    @property
    def local(self) -> bool:
        """
        Retrieve whether the history file location is a local path. If this is
        `False`, the location is instead a networked URL.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def __str__(self) -> str:
        return self._location

class Url(Location):
    """
    Remote, accessible URL to a history file.
    """

    @property
    def local(self) -> bool:
        return False

class Data_Source:
    """
    Object holding properties, path/URL, and possibly open file descriptor
    for one or more history data sources.
    """

    def __init__(self, sources: Set[Source],
                 locations: Union[Location, Sequence[Location]]) -> None:
        self._sources = sources
        if isinstance(locations, Location):
            self._locations: Tuple[Location, ...] = (locations,)
        elif not locations:
            raise ValueError('At least one location is required')
        else:
            self._locations = tuple(locations)

    @property
    def sources(self) -> Set[Source]:
        """
        Retrieve the source objects which were involved in locating the history
        of the measurements, or an empty list if there are no such source
        objects.
        """

        return self._sources

    @property
    def locations(self) -> Tuple[Location, ...]:
        """
        Retrieve a sequence of `Location` objects that provide some sort of
        access to the history file.
        """

        return self._locations

    @property
    def location(self) -> Location:
        """
        Retrieve the primary `Location` object from which the history file
        can be accessed.
        """

        return self._locations[0]

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        pass

def build_source(project: Project, location: Location, data: Data_Source) \
        -> Tuple[Source, str]:
    """
    Create a new source object based ona the information contained in a remote
    location.
    """

    environment_type = 'quality-time'
    source_type = 'quality-time'
    source_name = project.key

    for source in data.sources:
        if location.location == source.url:
            source_type = source.type
            environment_type = source.environment_type

    source = Source.from_type(source_type, name=source_name,
                              url=location.parts[0])
    return source, environment_type

def update_source(project: Project, data: Data_Source) -> None:
    """
    Replace the source domain objects involved in locating the measurements with
    another source which uses the full URL of the data source location in the
    project sources. If no such replacement can be made then the project sources
    are kept intact. Only sources with the same environment type are replaced.
    """

    for location in data.locations:
        if not location.local:
            source, environment_type = build_source(project, location, data)
            for old_source in data.sources:
                if old_source.environment_type == environment_type:
                    project.sources.discard(old_source)
            project.sources.add(source)

        project.export_sources()

def retrieve_metric_data(project: Project) -> Union[str, List[Dict[str, str]]]:
    """
    Retrieve metric data from the source or format an identifier for it.
    """

    metric_data: Union[str, List[Dict[str, str]]] = ''
    for source in project.project_definitions_sources:
        if isinstance(source, Quality_Time):
            start_date = "1901-01-01 00:00:00"
            date_path = project.export_key / 'quality_time_measurement_date.txt'
            if date_path.exists():
                with date_path.open('r') as date_file:
                    start_date = date_file.read()

            logging.info("Reading Quality Time measurements of %s", project.key)
            metric_data, latest_date = \
                read_quality_time_measurements(project, source,
                                               start_date=start_date)
            with date_path.open('w') as date_file:
                date_file.write(parse_date(latest_date))

            return metric_data

    return metric_data

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project_key = str(args.project)

    project = Project(project_key)

    metric_data: Union[str, List[Dict[str, str]]] = ''

    try:
        metric_data = retrieve_metric_data(project)
    except RuntimeError as error:
        logging.warning('Skipping quality metrics history import for %s: %s',
                        project_key, str(error))
        return

    output_path = project.export_key / 'data_metrics.json'
    with output_path.open('w') as outfile:
        json.dump(metric_data, outfile, indent=4)

if __name__ == "__main__":
    main()
