"""
Script to obtain the base names of all metrics used in HQ.
"""

import argparse
import json
import logging
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain quality metrics base names'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--project', default=None,
                        help='Project to retrieve HQ metrics for')
    parser.add_argument('--host', default=config.get("metrics", "host"),
                        help='Hostname to retrieve HQ metrics for')
    parser.add_argument('--url', default=config.get("metrics", "url"),
                        help='URL to retrieve HQ meta data from')
    parser.add_argument('--file', default='metrics_base_names.json',
                        help='Output file name')

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def parse_meta_data(data):
    """
    Retrieve metric base names from metadata.
    """

    return [metric["id"] for metric in data["metrics"]]

def parse_metrics(data):
    """
    Retrieve metric base names from metrics.
    """

    return list(set(metric["metric_class"] for metric in data["metrics"]))

def main():
    """
    Main entry point.
    """

    args = parse_args()
    url = args.url
    meta_data = True

    if args.project is not None:
        project = Project(args.project)
        if project.quality_metrics_name is not None:
            url = '{}/{}/json/metrics.json'.format(args.host,
                                                   project.quality_metrics_name)
            meta_data = False

    try:
        request = Session().get(url)
        request.raise_for_status()
    except (ConnectError, HTTPError, Timeout):
        logging.exception('Could not obtain metrics base names')
        return

    try:
        data = request.json()
    except ValueError:
        logging.exception('Could not parse metrics base names')
        return

    if meta_data:
        base_names = parse_meta_data(data)
    else:
        base_names = parse_metrics(data)

    with open(args.file, 'w') as output_file:
        json.dump(base_names, output_file)

if __name__ == '__main__':
    main()
