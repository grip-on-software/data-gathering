"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.

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
import logging

from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Metric_Options_Collector

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain quality metric project definition and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--url", default=None,
                        help="Override project definitions source URL")
    parser.add_argument("--from-revision", dest="from_revision", default=None,
                        help="Revision to start from gathering definitions")
    parser.add_argument("--to-revision", dest="to_revision", default=None,
                        help="Revision to stop gathering definitions at")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()

    project_key = args.project
    project = Project(project_key)
    if project.quality_metrics_name is None:
        logging.warning('No metrics options available for %s, skipping.',
                        project_key)
        return

    for source in project.project_definitions_sources:
        try:
            collector = Metric_Options_Collector(project, source, url=args.url)
            collector.collect(args.from_revision, args.to_revision)
        except RuntimeError:
            logging.exception('Could not collect metric options of %s',
                              project_key)

if __name__ == "__main__":
    main()
