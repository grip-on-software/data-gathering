"""
Script to obtain the base names of all metrics used in HQ.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University

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
import json
import logging
from typing import Any, Dict, List
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain quality metrics base names'
    parser = ArgumentParser(description=description)
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

def parse_meta_data(data: Dict[str, Any]) -> List[str]:
    """
    Retrieve metric base names from metadata.
    """

    return [metric["id"] for metric in data["metrics"]]

def parse_metrics(data: Dict[str, Any]) -> List[str]:
    """
    Retrieve metric base names from metrics.
    """

    return list({metric["metric_class"] for metric in data["metrics"]})

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    url = str(args.url)
    meta_data = True

    if args.project is not None:
        project = Project(args.project)
        base_name = project.quality_metrics_name
        if base_name is not None:
            url = f'{args.host}/{base_name}/json/metrics.json'
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

    with open(args.file, 'w', encoding='utf-8') as output_file:
        json.dump(base_names, output_file)

if __name__ == '__main__':
    main()
