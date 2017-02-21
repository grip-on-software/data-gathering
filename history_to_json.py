"""
Script to obtain a metrics history file and convert it to a JSON format
readable by the database importer.
"""

import argparse
import ConfigParser
from contextlib import contextmanager
import ast
import gzip
import io
import itertools
import json
import logging
import os
# Non-standard imports
import requests
from gatherer.domain import Project
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
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=None,
                       help="url prefix to obtain the file from")
    group.add_argument("--export-url", default=None, dest="export_url",
                       nargs='?', const=True,
                       help="url prefix to use as a reference rather than reading all data")
    group.add_argument("--file", help="local file to read from")
    return parser.parse_args()

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

    print 'Number of lines read: {}'.format(str(line_count))
    print 'Number of new metric values: {}'.format(str(len(metric_data)))
    return metric_data, line_count

def make_url(project, url_prefix):
    """
    Create a URL to the metrics history file for the given project.
    """

    project_name = project.quality_metrics_name
    if project_name is None:
        raise RuntimeError('No metrics history file URL available')

    return url_prefix + project_name + "/history.json.gz"

@contextmanager
def get_data_source(project, args):
    """
    Yield an open file containing the historical metric values of the project.
    """

    if args.file is not None:
        yield open(args.file, 'r')
    else:
        config = ConfigParser.RawConfigParser()
        config.read("settings.cfg")
        if config.has_option('history', project.key):
            default_url_prefix = config.get('history', project.key)
        else:
            default_url_prefix = config.get('history', 'url')

        if args.export_url is not None:
            if args.export_url is True:
                export_url = default_url_prefix
            else:
                export_url = args.export_url

            yield make_url(project, export_url)
        else:
            if args.url is None:
                url_prefix = default_url_prefix
            else:
                url_prefix = args.url

            url = make_url(project, url_prefix)
            request = requests.get(url)
            stream = io.BytesIO(request.content)
            yield gzip.GzipFile(mode='r', fileobj=stream)

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
            if isinstance(data, str):
                metric_data = '{0}#{1}'.format(data, start_from)
                line_count = 0
            else:
                metric_data, line_count = read_project_file(data, start_from)
    except RuntimeError as error:
        logging.warning('Skipping quality metrics history import for %s: %s',
                        project_key, error.message)
        return

    output_filename = os.path.join(project.export_key, 'data_metrics.json')
    with open(output_filename, 'w') as outfile:
        json.dump(metric_data, outfile, indent=4)

    with open(line_filename, 'w') as line_file:
        line_file.write(bytes(start_from + line_count))

if __name__ == "__main__":
    main()
