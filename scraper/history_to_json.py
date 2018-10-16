"""
Script to obtain a metrics history file and convert it to a JSON format
readable by the database importer.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import str
from past.builtins import basestring
import argparse
from contextlib import contextmanager
import ast
import gzip
import io
import itertools
import json
import logging
import os
import shutil
# Non-standard imports
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import Source
from gatherer.domain.source.gitlab import GitLab
from gatherer.domain.source.history import History
from gatherer.log import Log_Setup
from gatherer.utils import parse_date
from gatherer.request import Session

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain a metrics history file and output JSON"
    parser = argparse.ArgumentParser(description=description)
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

def read_project_file(data_file, start_from=0):
    """
    Read metric data from a project history file.

    The `data_file` is an open file or similar stream from which we can read
    the lines of metrics results. `start_from` indicates the line at which we
    start reading new metrics data.
    """

    metric_data = []
    line_count = 0

    for row in itertools.islice(data_file, start_from, None):
        line_count += 1
        if row.strip() == "":
            continue

        metric_row = ast.literal_eval(row)
        date = parse_date(metric_row["date"])
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

def get_setting(arg, key, project, boolean=False):
    """
    Retrieve a configuration setting from the history section using the `key`
    as well as the project key for the option name, using multiple variants.

    If `arg` is set to a valid setting then this value is used instead.

    If `boolean` is `True`, then configuration settings (not provided via `arg`)
    are casted to boolean via `Configuration.has_value`.
    """

    project_name = project.quality_metrics_name
    if project_name is None:
        raise RuntimeError('No metrics history file URL available')

    if arg is None or arg is True:
        setting = project.get_key_setting('history', key, project_name)
        has_value = Configuration.has_value(setting)
        if boolean:
            return has_value
        if has_value:
            return setting

    return arg

def check_sparse_base(export_path):
    """
    Determine whether the export directory is a sparse base directory, where
    a repository containing multiple project's histories are cloned to.
    """

    return '/' not in export_path.rstrip('/')

def get_gitlab_url(project, args):
    """
    Check whether the provided export URL and if so, whether the repository
    would be cloned to a sparse base directory. Return a URL that can be
    used to download the history file for the project, which may be situated
    in a subpath in the repository.
    """

    export_url = get_setting(args.export_url, 'url', project)
    if not Configuration.has_value(export_url):
        return None

    if not GitLab.is_gitlab_url(export_url):
        return (export_url,)

    parts = [export_url, "raw/master"]

    repo_path = get_setting(args.export_path, 'path', project)
    if Configuration.has_value(repo_path) and check_sparse_base(repo_path):
        parts.append(project.quality_metrics_name)

    return parts

def get_gitlab_path(project, args):
    """
    Check if the arguments or settings have a GitLab URL. If so, clone the
    repository containing the metrics history from there.

    Returns a tuple, consisting of the most directly known path to the cloned
    history file and the GitLab URL it is cloned from. If no GitLab repository
    was found, then the provided `export_path` argument or setting and `None`
    is returned. If the argument or setting is not provided, then two `None`
    values are returned.
    """

    export_path = get_setting(args.export_path, 'path', project)
    if not Configuration.has_value(export_path):
        return None, None

    gitlab_url = get_setting(args.url, 'url', project)
    if not Configuration.has_value(gitlab_url):
        return export_path, None
    if not GitLab.is_gitlab_url(gitlab_url):
        return export_path, None

    delete = get_setting(args.delete, 'delete', project, boolean=True)
    if delete and os.path.exists(export_path):
        logging.info('Removing old history clone %s', export_path)
        shutil.rmtree(export_path)

    if check_sparse_base(export_path):
        paths = [project.quality_metrics_name]
        clone_path = os.path.join(export_path, project.quality_metrics_name)
        git_path = os.path.join(export_path, '.git')
        if os.path.exists(export_path) and not os.path.exists(git_path):
            # The sparse clone has not yet been created (no .git directory)
            # but it must be placed in the root directory of the clones.
            # The other clones must be removed before the clone operation.
            logging.info('Making way to clone into %s', export_path)
            shutil.rmtree(export_path)
    else:
        paths = None
        clone_path = export_path

    logging.info('Pulling quality metrics history repository to %s',
                 export_path)
    source = Source.from_type('gitlab', name='quality-report-history',
                              url=gitlab_url)
    repo_class = source.repository_class
    repo_class.from_source(source, export_path, checkout=paths,
                           shallow=True, progress=True)
    return clone_path, gitlab_url

class Location(object):
    """
    Location of a history file.
    """

    def __init__(self, parts, filename=None, compression=False):
        if isinstance(parts, basestring):
            parts = (parts,)

        if filename is not None:
            parts = tuple(parts) + (filename,)
        self._parts = tuple(parts)
        self._location = "/".join(parts)
        self._compression = compression

    @property
    def parts(self):
        """
        Retrieve the parts of the path or URL that were used to find the
        location of the history file.
        """

        return self._parts

    @property
    def location(self):
        """
        Retrieve the path or URL to the history file.
        """

        return self._location

    @property
    def local(self):
        """
        Retrieve whether the history file location is a local path. If this is
        `False`, the location is instead a networked URL.
        """

        raise NotImplementedError('Must be implemented by subclass')

    @property
    def compression(self):
        """
        Retrieve the compression used of the file or a falsy value if the file
        has no compression.
        """

        return self._compression

    def __str__(self):
        return self._location

class Path(Location):
    """
    Local filesystem path to a history file.
    """

    @property
    def local(self):
        return True

class Url(Location):
    """
    Remote, accessible URL to a history file.
    """

    @property
    def local(self):
        return False

class Data_Source(object):
    """
    Object holding properties, path/URL, and possibly open file descriptor
    for one or more history data sources.
    """

    def __init__(self, sources, locations, open_file=None):
        self._sources = sources
        if isinstance(locations, Location):
            self._locations = (locations,)
        elif len(locations) < 1:
            raise ValueError('At least one location is required')
        else:
            self._locations = tuple(locations)

        self._file = open_file

    @property
    def sources(self):
        """
        Retrieve the `History` source objects which were involved in locating
        the history file, or an empty list if there are no such source objects.
        """

        return self._sources

    @property
    def locations(self):
        """
        Retrieve a sequence of `Location` objects that provide some sort of
        access to the history file.
        """

        return self._locations

    @property
    def location(self):
        """
        Retrieve the primary `Location` object from which the history file
        can be accessed.
        """

        return self._locations[0]

    @property
    def file(self):
        """
        Retrieve an open file descriptor for the history file, or `None` if
        the file is not opened.
        """

        return self._file

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if self._file is not None:
            self._file.close()
            self._file = None

def get_filename(project, sources, args):
    """
    Retrieve the file name of the history file. This name, without any preceding
    paths, may be set from a command line argument, the history sources, or the
    (project-specific) settings configuration, in that order of precedence.
    """

    if args.filename is not None:
        return args.filename

    for source in sources:
        if source.file_name is not None:
            return source.file_name

    return project.get_key_setting('history', 'filename')

def get_filename_compression(project, sources, args):
    """
    Retrieve the file name of the history file and the compression to be used
    to read the file. The file name is adjusted to contain the compression
    extension.
    """

    filename = get_filename(project, sources, args)
    compression = get_setting(args.compression, 'compression', project)
    if compression and os.path.splitext(filename)[1] != compression:
        filename += "." + compression

    return filename, compression

def get_file_opener(compression):
    """
    Retrieve a method or class that, when called, returns an open file object
    applicable for the given `compression`, which may be `None` or `False` to
    indicate no compression. The returned callable object can be called with
    a filename and a mode argument, in that order, or when `compression` is
    not `None`, an open file object through keyword argument `fileobj`.

    Raises a `ValueError` if the compression is not supported.
    """

    if not compression:
        return open
    if compression == "gz":
        return gzip.GzipFile

    raise ValueError("Compression '{}' is not supported".format(compression))

@contextmanager
def get_data_source(project, args):
    """
    Yield a path, URL or a read-only opened file containing the historical
    metric values of the project. When used as a context manager in a 'with'
    statement, any opened file is closed upon exiting the 'with' block.
    """

    # Retrieve the history file name as defined in the source, or from other
    # environment settings. See `get_filename` for details. We adjust the
    # filename to contain the compression extension if it did not have one;
    # note that we do not remove extensions if compression is disabled.
    sources = set(project.sources.find_sources_by_type(History))
    filename, compression = get_filename_compression(project, sources, args)

    if args.export_path is not None:
        # Path to a local directory or a repository target for a GitLab URL.
        # The local directory contains history.json.gz or the GitLab repository
        # contains it in its root or possibly in a subdirectory matching the
        # quality dashboard name.
        export_path, gitlab_url = get_gitlab_path(project, args)
        if export_path is not None and os.path.exists(export_path):
            locations = [Path(export_path, filename, compression)]
            if gitlab_url is not None:
                locations.append(Url(gitlab_url, compression=compression))
            logging.info('Found metrics history path: %s', locations[0])
            yield Data_Source(sources, locations)
            return
    elif args.path is not None:
        # Path to a directory with a local file that can be opened.
        path = Path(args.path, filename, compression)
        opener = get_file_opener(compression)
        yield Data_Source(sources, path, open_file=opener(path, 'r'))
        return

    if args.export_url is not None:
        # URL or a GitLab repository that can be accessed in an unauthenticated
        # manner by the importer.
        parts = get_gitlab_url(project, args)
        if parts is not None:
            url = Url(parts, filename, compression)
            logging.info('Found metrics history URL: %s', url)
            yield Data_Source(sources, url)
            return
    elif args.url is not None:
        # URL prefix to a specific download location.
        url_prefix = get_setting(args.url, 'url', project)
        url = Url(url_prefix, filename, compression)
        stream = io.BytesIO(Session().get(url).content)
        if compression:
            opener = get_file_opener(compression)
            open_file = opener(mode='r', fileobj=stream)
        else:
            open_file = stream

        yield Data_Source(sources, url, open_file=open_file)
        return

    raise RuntimeError('No valid metrics history source defined')

def get_tracker_start(args):
    """
    Retrieve an indicator of where to start reading from in the history file.
    """

    if args.start_from is not None:
        return args.start_from

    start_filenames = ['history_record_time.txt', 'history_line_count.txt']
    start_from = 0
    for filename in start_filenames:
        if os.path.exists(filename):
            with open(filename, 'r') as start_file:
                start_from = int(start_file.read())

            break

    return start_from

def update_source(project, data):
    """
    Replace the `History` source domain object in the project sources with
    another source which uses the full URL of the data source location, if
    possible.
    """

    for location in data.locations:
        if not location.local:
            source_name = project.key
            file_name = ''
            for source in data.sources:
                if source.file_name is not None:
                    source_name = source.name
                    file_name = source.file_name
                    break

            url = '{}/{}'.format(location.parts[0], file_name)
            new_source = Source.from_type('metric_history',
                                          name=source_name,
                                          url=url)
            for source in data.sources:
                project.sources.remove(source)
            project.sources.add(new_source)
            project.export_sources()

            break

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project

    project = Project(project_key)

    # Check most recent history format tracker first
    start_from = get_tracker_start(args)

    try:
        with get_data_source(project, args) as data:
            update_source(project, data)

            if args.compact is not None:
                is_compact = args.compact
            elif any(source.is_compact for source in data.sources):
                is_compact = True
            else:
                is_compact = False

            if data.file is None:
                flags = [str(start_from)]
                if data.location.local:
                    flags.append('local')
                if is_compact:
                    flags.append('compact')

                if data.location.compression:
                    flags.append('compression={}'.format(data.location.compression))
                else:
                    flags.append('compression=')

                metric_data = '{0}#{1}'.format(str(data.location), '|'.join(flags))
            elif is_compact:
                raise RuntimeError('Cannot read compact history during gather')
            else:
                metric_data, line_count = read_project_file(data.file,
                                                            int(start_from))
                line_filename = os.path.join(project.export_key, 'history_line_count.txt')
                with open(line_filename, 'w') as line_file:
                    line_file.write(str(start_from + line_count))
    except RuntimeError as error:
        logging.warning('Skipping quality metrics history import for %s: %s',
                        project_key, str(error))
        return

    output_filename = os.path.join(project.export_key, 'data_metrics.json')
    with open(output_filename, 'w') as outfile:
        json.dump(metric_data, outfile, indent=4)

if __name__ == "__main__":
    main()
