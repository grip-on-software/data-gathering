"""
Script to obtain version control data from repositories and output JSON readable
by the database importer.

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
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.version_control.holder import Repositories_Holder

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain repository versions and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repos", default="project-git-repos",
                        help="directory containing the project repositories")
    parser.add_argument("--ignore-host-change", dest="follow_host_change",
                        action="store_false", default=True,
                        help="Ignore credential host changes and use the original host instead")
    parser.add_argument("--force", action="store_true", default=False,
                        help="Delete and clone repository is pull fails")
    parser.add_argument("--no-pull", action="store_false", default=True,
                        dest="pull", help="Do not pull existing repositories")
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
    project = Project(args.project, follow_host_change=args.follow_host_change)

    holder = Repositories_Holder(project, args.repos)
    holder.process(force=args.force, pull=args.pull)

if __name__ == "__main__":
    main()
