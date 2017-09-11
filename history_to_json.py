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
import requests
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import Source
from gatherer.domain.source.gitlab import GitLab
from gatherer.domain.source.history import History
from gatherer.log import Log_Setup
from gatherer.utils import parse_date

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

def make_path(prefix, filename):
    """
    Create a path or URL to the metrics history file.
    """

    return prefix + "/" + filename

def get_setting(arg, key, project):
    """
    Retrieve a configuration setting from the history section using the `key`
    as well as the project key for the option name, using multiple variants.

    If `arg` is set to a valid setting then this value is used instead.
    """

    project_name = project.quality_metrics_name
    if project_name is None:
        raise RuntimeError('No metrics history file URL available')

    if arg is None or arg is True:
        return project.get_key_setting('history', key, project_name)

    return arg

def check_sparse_base(export_path):
    """
    Determine whether the export directory is a sparse base directory, where
    a repository containing multiple project's histories are cloned to.
    """

    return '/' not in export_path.rstrip('/')

def check_gitlab_url(project, args, export_url):
    """
    Check whether the provided export URL and if so, whether the repository
    would be cloned to a sparse base directory. Return a URL that can be
    used to download the history file for the project, which may be situated
    in a subpath in the repository.
    """

    if GitLab.is_gitlab_url(export_url):
        export_url = export_url + "/raw/master"

        repo_path = get_setting(args.export_path, 'path', project)
        if Configuration.has_value(repo_path) and check_sparse_base(repo_path):
            return export_url + "/" + project.quality_metrics_name

    return export_url

def check_gitlab_path(project, args, export_path):
    """
    Check if the arguments or settings have a GitLab URL. If so, clone the
    repository containing the metrics history from there.

    Returns the most directly known path to the cloned history file, or the
    provided `export_path` if no GitLab repository was found.
    """

    gitlab_url = get_setting(args.url, 'url', project)
    if Configuration.has_value(gitlab_url) and GitLab.is_gitlab_url(gitlab_url):
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
        return clone_path

    return export_path

class Data_Source(object):
    """
    Object holding properties, path or URL, and possibly open file descriptor
    for a history data source.
    """

    def __init__(self, source, location, local=True, open_file=None):
        self._source = source
        self._location = location
        self._local = local
        self._file = open_file

    @property
    def source(self):
        """
        Retrieve the `History` source object which was involved in locating
        the history file, or `None` if there is no such source object.
        """

        return self._source

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

        return self._local

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

def get_filename(project, source, args):
    """
    Retrieve the file name of the history file. This name, without any preceding
    paths, may be set from a command line argument, the history source, or the
    (project-specific) settings configuration, in that order of precedence.
    """

    if args.filename is not None:
        return args.filename

    if source is not None:
        return source.file_name

    return project.get_key_setting('history', 'filename')

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
    source = project.sources.find_source_type(History)
    filename = get_filename(project, source, args)
    compression = get_setting(args.compression, 'compression', project)
    if compression and os.path.splitext(filename)[1] != compression:
        filename += "." + compression

    if args.export_path is not None:
        # Path to a local directory or a repository target for a GitLab URL.
        # The local directory contains history.json.gz or the GitLab repository
        # contains it in its root or possibly in a subdirectory matching the
        # quality dashboard name.
        export_path = get_setting(args.export_path, 'path', project)
        if Configuration.has_value(export_path):
            export_path = check_gitlab_path(project, args, export_path)
            if os.path.exists(export_path):
                logging.info('Found metrics history path: %s', export_path)
                yield Data_Source(source, make_path(export_path, filename),
                                  local=True)
                return
    elif args.path is not None:
        # Path to a directory with a local file that can be opened.
        path = make_path(args.path, filename)
        opener = get_file_opener(compression)

        yield Data_Source(source, path, local=True, open_file=opener(path, 'r'))
        return

    if args.export_url is not None:
        # URL or a GitLab repository that can be accessed in an unauthenticated
        # manner by the importer.
        export_url = get_setting(args.export_url, 'url', project)
        if Configuration.has_value(export_url):
            export_url = check_gitlab_url(project, args, export_url)
            logging.info('Found metrics history URL: %s', export_url)
            yield Data_Source(source, make_path(export_url, filename),
                              local=False)
    elif args.url is not None:
        # URL prefix to a specific download location.
        url_prefix = get_setting(args.url, 'url', project)
        url = make_path(url_prefix, filename)
        request = requests.get(url)
        stream = io.BytesIO(request.content)
        if compression:
            opener = get_file_opener(compression)
            open_file = opener(mode='r', fileobj=stream)
        else:
            open_file = stream

        yield Data_Source(source, url, local=False, open_file=open_file)
    else:
        raise RuntimeError('No metrics history source defined')

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
            if args.compact is not None:
                is_compact = args.compact
            elif data.source is not None and data.source.is_compact:
                is_compact = True
            else:
                is_compact = False

            if data.file is None:
                flags = [str(start_from)]
                if data.local:
                    flags.append('local')
                if is_compact:
                    flags.append('compact')

                metric_data = '{0}#{1}'.format(data.location, '|'.join(flags))
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
