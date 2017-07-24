"""
Script to obtain a metrics history file and convert it to a JSON format
readable by the database importer.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from past.builtins import basestring
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
from gatherer.domain.source import Source, GitLab
from gatherer.log import Log_Setup
from gatherer.utils import parse_date

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain a metrics history file and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--start-from", dest="start_from", type=int,
                        default=None, help="line number to start reading from")

    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument("--url", default=None,
                           help="url prefix to obtain the file from")
    url_group.add_argument("--export-url", default=None, dest="export_url",
                           nargs='?', const=True,
                           help="url prefix to use as a reference rather than reading all data")
    path_group = parser.add_mutually_exclusive_group()
    path_group.add_argument("--file", default=None,
                            help="local file to read from")
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

def make_path(prefix):
    """
    Create a path or URL to the metrics history file.
    """

    return prefix + "/history.json.gz"

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

@contextmanager
def get_data_source(project, args):
    """
    Yield a path, URL or a read-only opened file containing the historical
    metric values of the project. When used as a context manager in a 'with'
    statement, any opened file is closed upon exiting the 'with' block.
    """

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
                yield make_path(export_path) + "|"
                return
    elif args.file is not None:
        # Path to a local uncompressed file that can be opened
        yield open(args.file, 'r')
        return

    if args.export_url is not None:
        # URL to a specific GZIP file or a GitLab repository that can be
        # accessed in an unauthenticated manner by the importer.
        export_url = get_setting(args.export_url, 'url', project)
        if Configuration.has_value(export_url):
            export_url = check_gitlab_url(project, args, export_url)
            logging.info('Found metrics history URL: %s', export_url)
            yield make_path(export_url)
    elif args.url is not None:
        # URL to a specific GZIP file download.
        url_prefix = get_setting(args.url, 'url', project)
        url = make_path(url_prefix)
        request = requests.get(url)
        stream = io.BytesIO(request.content)
        yield gzip.GzipFile(mode='r', fileobj=stream)
    else:
        raise RuntimeError('No metrics history source defined')

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    start_from = args.start_from

    project = Project(project_key)

    line_filename = os.path.join(project.export_key, 'history_line_count.txt')
    if start_from is None:
        if os.path.exists(line_filename):
            with open(line_filename, 'r') as line_file:
                start_from = int(line_file.read())
        else:
            start_from = 0

    try:
        with get_data_source(project, args) as data:
            if isinstance(data, basestring):
                metric_data = '{0}#{1}'.format(data, start_from)
                line_count = 0
            else:
                metric_data, line_count = read_project_file(data, start_from)
    except RuntimeError as error:
        logging.warning('Skipping quality metrics history import for %s: %s',
                        project_key, str(error))
        return

    output_filename = os.path.join(project.export_key, 'data_metrics.json')
    with open(output_filename, 'w') as outfile:
        json.dump(metric_data, outfile, indent=4)

    with open(line_filename, 'w') as line_file:
        line_file.write(str(start_from + line_count))

if __name__ == "__main__":
    main()
