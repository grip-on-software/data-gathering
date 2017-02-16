"""
Script to parse current project definitions and extract metric sources from
the products and components.
"""

import argparse
import json

from gatherer.project_definition import Sources_Parser
from gatherer.domain import Project, Source

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain project sources definition"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default="kwaliteitsmetingen/trunk",
                        help="Subversion directory with project definitions")

    return parser.parse_args()

def parse_sources(project_key, sources):
    """
    Given a list of source repositories parsed from the project definition,
    output data that can be used by other gatherer scripts.
    """

    data = []
    for name, metric_source in sources.items():
        if 'Subversion' in metric_source:
            source = Source('subversion', name=name, url=metric_source['Subversion'])
        elif 'Git' in metric_source:
            source = Source('git', name=name, url=metric_source['Git'])
        else:
            continue

        data.append(source.export())

    with open(project_key + '/data_sources.json', 'w') as sources_file:
        json.dump(data, sources_file)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    project = Project(project_key)

    project_name = project.quality_metrics_name
    if project_name is None:
        if project.main_project is not None:
            reason = 'main project is {}'.format(project.main_project)
        else:
            reason = 'no long name or main project defined'
        print 'No project sources available for {} ({}), skipping.'.format(project_key, reason)
        return

    filename = args.repo + '/' + project_name + '/project_definition.py'
    parser = Sources_Parser(args.repo)

    with open(filename, 'r') as definition_file:
        parser.load_definition(definition_file.read())

    sources = parser.parse()
    parse_sources(project_key, sources)

if __name__ == "__main__":
    main()
