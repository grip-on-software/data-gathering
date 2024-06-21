"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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
from gatherer.project_definition.collector import Metric_Options_Collector, \
    Metric_Defaults_Collector

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
    parser.add_argument("--defaults", action="store_true", default=None,
                        help="Force collecting metric defaults as well")
    parser.add_argument("--no-defaults", action="store_false", dest="defaults",
                        help="Disable collecting metric defaults even if fast")

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
        data_model = None
        try:
            options = Metric_Options_Collector(project, source, url=args.url)
            options.collect(args.from_revision, args.to_revision)
            data_model = options.data_model
        except RuntimeError:
            logging.exception('Could not collect metric options of %s',
                              project_key)

        if args.defaults or (args.defaults is None and data_model is not None):
            try:
                defaults = Metric_Defaults_Collector(project, source,
                                                     url=args.url,
                                                     data_model=data_model)
                defaults.collect(args.from_revision, args.to_revision)
            except RuntimeError:
                logging.exception('Could not collect metric defaults of %s',
                                  project_key)

if __name__ == "__main__":
    main()
