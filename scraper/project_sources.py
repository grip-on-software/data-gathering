"""
Script to parse current project definitions and extract metric sources from
the products and components.

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
import logging
import os

from gatherer.log import Log_Setup
from gatherer.project_definition.collector import Sources_Collector
from gatherer.domain import Project

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain project sources definition"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default=None,
                        help="Project definitions repository directory or URL")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--all", action="store_true", default=False,
                        help="retrieve all updated versions of the definition")
    parser.add_argument("--from-revision", dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", dest="to_revision", default=None,
                        help="revision to stop gathering definitions at")

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project_key = str(args.project)
    project = Project(project_key)

    # Clear the existing project sources such that we only take the ones that
    # are retrieved in this run; dropins are kept though.
    if os.getenv('skip_dropin') != '0':
        project.sources.clear()

    project_name = project.quality_metrics_name
    if project_name is None:
        if project.main_project is not None:
            reason = f'main project is {project.main_project}'
        else:
            reason = 'no long name or main project defined'

        logging.warning('No project sources available for %s (%s), skipping.',
                        project_key, reason)
        project.export_sources()
        return

    for source in project.project_definitions_sources:
        try:
            collector = Sources_Collector(project, source, repo_path=args.repo,
                                          context_lines=args.context)
            if args.all or args.from_revision is not None or args.to_revision is not None:
                collector.collect(args.from_revision, args.to_revision)
            else:
                collector.collect_latest()
        except RuntimeError:
            logging.exception('Could not collect project sources for %s',
                              project_key)

    project.export_sources()

if __name__ == "__main__":
    main()
