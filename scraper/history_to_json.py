"""
Script to obtain a metrics history file and convert it to a JSON format
readable by the database importer.
"""

from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
import ast
from datetime import datetime
import gzip
import io
import itertools
import json
import logging
import os
from pathlib import Path, PurePath
import shutil
from types import TracebackType
from typing import Any, Callable, Dict, Generator, List, Optional, Sequence, \
    Set, Tuple, Type, Union, TYPE_CHECKING
# Non-standard imports
from gatherer.config import Configuration
from gatherer.domain import Project, Source
from gatherer.domain.source import GitLab, History, Quality_Time
from gatherer.log import Log_Setup
from gatherer.project_definition.base import MetricNames, UUID
from gatherer.project_definition.data import Quality_Time_Data
from gatherer.utils import get_utc_datetime, parse_date
from gatherer.request import Session

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

    description = "Obtain a metrics history file and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--start-from", dest="start_from",
                        default=None, help="record to start reading from")
    parser.add_argument("--filename", default=None,
                        help="filename of the history file")
    parser.add_argument("--compact", action="store_true", default=None,
                        help="read the history file as a compact file")
    parser.add_argument("--no-compact", action="store_false", dest="compact",
                        help="read the history file as a legacy file")
    parser.add_argument("--compression", nargs="?", default=None, const="gz",
                        help="compression to use for the file")
    parser.add_argument("--no-compression", action="store_false",
                        dest="compression",
                        help="do not use compression for the file")
    parser.add_argument("--delete", action="store_true", default=None,
                        help="Delete local repository before a shallow clone")
    parser.add_argument("--no-delete", action="store_false", dest="delete",
                        help="Update local repository via shallow fetch")

    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument("--url", default=None,
                           help="url prefix without filename to read from")
    url_group.add_argument("--export-url", default=None, dest="export_url",
                           nargs='?', const=True,
                           help="url prefix to use as a reference rather than reading all data")
    path_group = parser.add_mutually_exclusive_group()
    path_group.add_argument("--path", default=None,
                            help="path prefix without filename to read from")
    path_group.add_argument("--export-path", default=None, dest="export_path",
                            nargs='?', const=True,
                            help="path prefix to use as a reference rather than reading all data")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def read_project_file(data_file: IOLike, start_from: int = 0) \
        -> Tuple[List[Dict[str, str]], int]:
    """
    Read metric data from a project history file.

    The `data_file` is an open file or similar stream from which we can read
    the lines of metrics results. `start_from` indicates the line at which we
    start reading new metrics data.
    """

    metric_data = []
    line_count = 0

    for line in itertools.islice(data_file, start_from, None):
        row = str(line)
        line_count += 1
        if row.strip() == "":
            continue

        metric_row: MetricRow = ast.literal_eval(row)
        date = parse_date(str(metric_row["date"]))
        for metric in metric_row:
            if isinstance(metric_row[metric], tuple):
                metric_row_data = {
                    'name': metric,
                    'value': metric_row[metric][0],
                    'category': metric_row[metric][1],
                    'date': date,
                    'since_date': parse_date(metric_row[metric][2])
                }
                metric_data.append(metric_row_data)

    logging.info('Number of lines read: %d', line_count)
    logging.info('Number of new metric values: %d', len(metric_data))
    return metric_data, line_count

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
    with metric_path.open('r') as metric_file:
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
    for measurement in data.get_measurements(metric_uuid, version):
        metric_row_data = parse_quality_time_measurement(metric_uuid,
                                                         measurement,
                                                         cutoff_date)
        if metric_row_data is not None:
            if isinstance(metrics, dict):
                metric = metrics[metric_uuid]
                if isinstance(metric, dict):
                    metric_row_data.update(metric)

            metric_data.append(metric_row_data)

    return metric_data

def parse_quality_time_measurement(metric_uuid: str,
                                   measurement: Dict[str, Any],
                                   cutoff_date: datetime) \
        -> Optional[Dict[str, str]]:
    """
    Parse a measurement of a Quality Time metric from its API.
    """

    date = parse_date(str(measurement.get("end")))
    if get_utc_datetime(date) <= cutoff_date:
        return None

    count = measurement.get("count", {})
    category = count.get("status")
    value = count.get("value")

    return {
        'name': metric_uuid,
        'value': str(value) if value is not None else "-1",
        'category': str(category) if category is not None else "unknown",
        'date': date,
        'since_date': parse_date(str(measurement.get("start")))
    }

def get_setting(arg: Any, key: str, project: Project, default: str = '') -> str:
    """
    Retrieve a configuration setting from the history section using the `key`
    as well as the project key for the option name, using multiple variants.

    If `arg` is set to a valid setting then this value is used instead.
    Only if `arg` is `None` (missing) or `True` (enabled) then the project key
    setting will be used if available, otherwise the `default` is returned.
    If `arg` is `False` then an empty string will be returned. In any case, the
    return value will be a string, which should only be used if additional
    value checks (e.g., valid URL, path or within a set of allowed values) is
    performed.
    """

    project_name = project.quality_metrics_name
    if project_name is None:
        raise RuntimeError('No metrics history file URL available')

    if arg is None or arg is True:
        setting = project.get_key_setting('history', key, project_name)
        if Configuration.has_value(setting):
            return setting

        return default

    if arg is False:
        return ''

    return str(arg)

def get_boolean_setting(arg: Any, key: str, project: Project) -> bool:
    """
    Check a configuration setting from the history section using the `key`
    as well as the project key for the option name, using multiple variants.

    If `arg` is set to a valid setting then this is used instead. The return
    value is a boolean.
    """

    return Configuration.has_value(get_setting(arg, key, project, default='1'))

def check_sparse_base(export_path: PathLike) -> bool:
    """
    Determine whether the export directory is a sparse base directory, where
    a repository containing multiple project's histories are cloned to.
    """

    return '/' not in str(export_path).rstrip('/')

def get_gitlab_url(project: Project, args: Namespace) -> Optional[Tuple[str, ...]]:
    """
    Check whether the provided export URL and if so, whether the repository
    would be cloned to a sparse base directory. Return a URL that can be
    used to download the history file for the project, which may be situated
    in a subpath in the repository.
    """

    if args.export_url is None:
        return None

    export_url = get_setting(args.export_url, 'url', project)
    if not Configuration.has_value(export_url):
        return None

    if not GitLab.is_gitlab_url(export_url):
        return (export_url,)

    parts = [str(export_url), "raw/master"]

    repo_path = get_setting(args.export_path, 'path', project)
    if Configuration.has_value(repo_path) and check_sparse_base(repo_path) and \
        project.quality_metrics_name is not None:
        parts.append(project.quality_metrics_name)

    return tuple(parts)

def get_gitlab_path(project: Project, args: Namespace) \
        -> Tuple[Optional[Path], Optional[str]]:
    """
    Check if the arguments or settings have a GitLab URL. If so, clone the
    repository containing the metrics history from there.

    Returns a tuple, consisting of the most directly known path to the cloned
    history file and the GitLab URL it is cloned from. If no GitLab repository
    was found, then the provided `export_path` argument or setting and `None`
    is returned. If the argument or setting is not provided, then two `None`
    values are returned.
    """

    if args.export_path is None:
        return None, None

    path = get_setting(args.export_path, 'path', project)
    if not Configuration.has_value(path):
        return None, None
    export_path = Path(path)

    gitlab_url = get_setting(args.url, 'url', project)
    if not Configuration.has_value(gitlab_url):
        return export_path, None
    if not GitLab.is_gitlab_url(gitlab_url):
        return export_path, None

    delete = get_boolean_setting(args.delete, 'delete', project)
    paths: Optional[List[str]] = None
    clone_path = export_path
    if check_sparse_base(export_path) and project.quality_metrics_name is not None:
        paths = [project.quality_metrics_name]
        clone_path = export_path / project.quality_metrics_name
        git_path = export_path / '.git'
        if not git_path.exists():
            # The sparse clone has not yet been created (no .git directory)
            # but it must be placed in the root directory of the clones.
            # The other clones must be removed before the clone operation.
            logging.info('Making way to clone sparsely into %s', export_path)
            delete = True

    if delete and export_path.exists():
        logging.info('Removing previous history clone %s', export_path)
        shutil.rmtree(str(export_path))

    logging.info('Pulling quality metrics history repository to %s',
                 export_path)
    source = GitLab('gitlab', name='quality-report-history', url=gitlab_url)
    repo_class = source.repository_class
    repo_class.from_source(source, export_path, checkout=paths,
                           shallow=True, pull=True, progress=True)
    return clone_path, gitlab_url

class Location:
    """
    Location of a history file.
    """

    def __init__(self, parts: Union[PathLike, Tuple[str, ...]],
                 filename: Optional[str] = None,
                 compression: Union[bool, str] = False) -> None:
        if isinstance(parts, (os.PathLike, str)):
            parts = (str(parts),)

        if filename is not None:
            parts = tuple(parts) + (filename,)
        self._parts = tuple(parts)
        self._location = "/".join(parts)
        self._compression = compression

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

    @property
    def compact(self) -> bool:
        """
        Retrieve whether the file is a compact history file.
        """

        return self._location.split('/')[-1] == 'compact-history.json'

    @property
    def compression(self) -> Union[bool, str]:
        """
        Retrieve the compression used of the file or a falsy value if the file
        has no compression.
        """

        return self._compression

    def __str__(self) -> str:
        return self._location

class File(Location):
    """
    Local filesystem path to a history file.
    """

    @property
    def local(self) -> bool:
        return True

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
                 locations: Union[Location, Sequence[Location]],
                 open_file: Optional[IOLike] = None) -> None:
        self._sources = sources
        if isinstance(locations, Location):
            self._locations: Tuple[Location, ...] = (locations,)
        elif not locations:
            raise ValueError('At least one location is required')
        else:
            self._locations = tuple(locations)

        self._file = open_file

    @classmethod
    def from_export_path(cls, gitlab_parts: Parts, sources: Set[Source],
                         locations: List[Location], filename: str,
                         compression: str) -> Optional['Data_Source']:
        """
        Create a data source object from a path to a local directory or
        a repository target for a GitLab URL.
        The local directory contains history.json.gz or the GitLab repository
        contains it in its root or possibly in a subdirectory matching the
        quality dashboard name.
        """

        if not isinstance(gitlab_parts, tuple) or len(gitlab_parts) != 2:
            return None

        export_path, gitlab_url = gitlab_parts
        if not isinstance(export_path, Path) or not export_path.exists():
            return None

        path = File(export_path, filename, compression)
        locations.append(path)
        if gitlab_url is not None:
            locations.append(Url(gitlab_url, compression=compression))
        logging.info('Found metrics history path: %s', path)
        return cls(sources, locations)

    @classmethod
    def from_path(cls, arg: Parts, sources: Set[Source],
                  locations: List[Location], filename: str,
                  compression: str) -> Optional['Data_Source']:
        """
        Create a data source object from a path to a directory with a local
        file that can be opened.
        """

        if not isinstance(arg, str):
            return None

        path = File(arg, filename, compression)
        locations.append(path)
        opener = get_file_opener(compression)
        return cls(sources, locations, open_file=opener(str(path), 'r'))

    @classmethod
    def from_export_url(cls, parts: Parts, sources: Set[Source],
                        locations: List[Location], filename: str,
                        compression: str) -> Optional['Data_Source']:
        """
        Create a data source object from a URL or a GitLab repository that
        can be accessed in an unauthenticated manner by the importer.
        """

        if parts is None:
            return None

        url = Url(tuple(str(part) for part in parts), filename, compression)
        locations.append(url)
        logging.info('Found metrics history URL: %s', url)
        return cls(sources, locations)

    @classmethod
    def from_url(cls, arg: Parts, sources: Set[Source],
                 locations: List[Location], filename: str,
                 compression: str) -> Optional['Data_Source']:
        """
        Create a data source object from a URL prefix to a specific download
        location.
        """

        if not isinstance(arg, str):
            return None

        url = Url(arg, filename, compression)
        locations.append(url)
        return cls(sources, locations, open_file=get_stream(compression, url))

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

    @property
    def file(self) -> Optional[IOLike]:
        """
        Retrieve an open file descriptor for the history file, or `None` if
        the file is not opened.
        """

        return self._file

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

def get_filename(project: Project, sources: Set[Source], args: Namespace) -> str:
    """
    Retrieve the file name of the history file. This name, without any preceding
    paths, may be set from a command line argument, the history sources, or the
    (project-specific) settings configuration, in that order of precedence.
    """

    if args.filename is not None:
        return str(args.filename)

    for source in sources:
        if source.file_name is not None:
            return str(source.file_name)

    return project.get_key_setting('history', 'filename')

def get_filename_compression(project: Project, sources: Set[Source],
                             args: Namespace) -> Tuple[str, str]:
    """
    Retrieve the file name of the history file and the compression to be used
    to read the file. The file name is adjusted to contain the compression
    extension.
    """

    filename = get_filename(project, sources, args)
    compression = get_setting(args.compression, 'compression', project)
    if compression and PurePath(filename).suffix[1:] != compression:
        filename += "." + compression

    return filename, compression

def get_file_opener(compression: Union[bool, str]) -> Type[OpenFile]:
    """
    Retrieve a method or class that, when called, returns an open file object
    applicable for the given `compression`, which may be `False` to
    indicate no compression. The returned class can be constructed with
    a filename and a mode argument, in that order, or when `compression` is
    not `False`, an open file object through keyword argument `fileobj`
    in the constructor.

    Raises a `ValueError` if the compression is not supported.
    """

    if not compression:
        return io.FileIO
    if compression == "gz":
        return gzip.GzipFile

    raise ValueError("Compression '{}' is not supported".format(compression))

def get_stream(compression: Union[bool, str], url: Url) -> IOLike:
    """
    Create a file descriptor for a URL source. Based on the compression,
    the open file may be a binary/compressed reader or string buffer.
    """

    response = Session().get(str(url))
    opener = get_file_opener(compression)
    if compression and isinstance(opener, gzip.GzipFile):
        return opener(mode='r', fileobj=io.BytesIO(response.content))

    return io.StringIO(response.text)

@contextmanager
def get_data_source(project: Project, args: Namespace) \
        -> Generator[Data_Source, None, None]:
    """
    Yield a path, URL or a read-only opened file containing the historical
    metric values of the project. When used as a context manager in a 'with'
    statement, any opened file is closed upon exiting the 'with' block.
    """

    # Retrieve the history file name as defined in the source, or from other
    # environment settings. See `get_filename` for details. We adjust the
    # filename to contain the compression extension if it did not have one;
    # note that we do not remove extensions if compression is disabled.
    sources: Set[Source] = set(project.sources.find_sources_by_type(History))
    locations: List[Location] = []
    for source in project.project_definitions_sources:
        if isinstance(source, Quality_Time):
            sources.add(source)
            locations.append(Url(source.url))

    filename, compression = get_filename_compression(project, sources, args)

    options: List[Tuple[Transform, Generate]] = [
        (get_gitlab_path, Data_Source.from_export_path),
        (lambda project, args: args.path, Data_Source.from_path),
        (get_gitlab_url, Data_Source.from_export_url),
        (lambda project, args: get_setting(args.url, 'url', project),
         Data_Source.from_url)
    ]

    for transform, method in options:
        parts = transform(project, args)
        if parts is not None:
            data = method(parts, sources, locations, filename, compression)
            if data is not None:
                yield data
                return

    if locations:
        yield Data_Source(sources, locations)
        return

    raise RuntimeError('No valid metrics history source defined')

def get_tracker_start(project: Project, args: Namespace) -> int:
    """
    Retrieve an indicator of where to start reading from in the history file.
    """

    if args.start_from is not None:
        return int(args.start_from)

    start_from = 0
    path = project.export_key / 'history_line_count.txt'
    if path.exists():
        with path.open('r') as start_file:
            start_from = int(start_file.read())

    return start_from

def build_source(project: Project, location: Location, data: Data_Source) \
        -> Tuple[Source, str]:
    """
    Create a new source object based ona the information contained in a remote
    location.
    """

    environment_type = 'metric_history'
    source_name = project.key
    if location.compact:
        source_type = 'compact-history'
        file_name = 'compact-history.json'
    else:
        source_type = 'metric_history'
        file_name = ''

    for source in data.sources:
        if source.environment_type != 'metric_history' and \
            location.location == source.url:
            source_type = source.environment_type
            environment_type = source_type
        if source.file_name is not None:
            source_name = source.name
            file_name = source.file_name
            if is_compact(source):
                source_type = 'compact-history'

            break

    url = '{}/{}'.format(location.parts[0], file_name)
    source = Source.from_type(source_type, name=source_name, url=url)
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

def is_compact(source: Source) -> bool:
    """
    Retrieve whether the history source is in a compact format.
    """

    if source.type == 'compact-history':
        return True

    if source.file_name is not None:
        return source.file_name.startswith('compact-history.json')

    return False

def build_metric_url(data: Data_Source, start_from: int, compact: bool) -> str:
    """
    Build a URL from a data source including an anchor that can be parsed
    to determine how to open the source.
    """

    flags = [str(start_from)]
    if data.location.local:
        flags.append('local')
    if compact or data.location.compact:
        flags.append('compact')

    if data.location.compression:
        flags.append(f'compression={data.location.compression}')
    else:
        flags.append('compression=')

    anchor = '|'.join(flags)
    return f'{data.location}#{anchor}'

def retrieve_metric_data(project: Project, data: Data_Source, start_from: int,
                         compact: bool) -> Union[str, List[Dict[str, str]]]:
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

    if data.file is None:
        return build_metric_url(data, start_from, compact)

    if compact:
        raise RuntimeError('Cannot read compact history during gather')

    metric_data, line_count = read_project_file(data.file, start_from)
    line_path = project.export_key / 'history_line_count.txt'
    with line_path.open('w') as line_file:
        line_file.write(str(start_from + line_count))

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
        with get_data_source(project, args) as data:
            update_source(project, data)

            if args.compact is not None:
                compact = bool(args.compact)
            else:
                compact = any(is_compact(source) for source in data.sources)

            start = get_tracker_start(project, args)
            metric_data = retrieve_metric_data(project, data, start, compact)
    except RuntimeError as error:
        logging.warning('Skipping quality metrics history import for %s: %s',
                        project_key, str(error))
        return

    output_path = project.export_key / 'data_metrics.json'
    with output_path.open('w') as outfile:
        json.dump(metric_data, outfile, indent=4)

if __name__ == "__main__":
    main()
