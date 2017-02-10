"""
Script to parse current project definitions and extract metric sources from
the products and components.
"""

import argparse
import ConfigParser

from gatherer.project_definition import Sources_Parser

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

def main():
    """
    Main entry point.
    """

    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")
    args = parse_args()

    project_key = args.project
    if config.has_option('projects', project_key):
        project_name = config.get('projects', project_key)
    else:
        print 'No quality metrics options available for {}, skipping.'.format(project_key)
        return

    filename = args.repo + '/' + project_name + '/project_definition.py'
    parser = Sources_Parser(args.repo)

    with open(filename, 'r') as definition_file:
        parser.load_definition(definition_file.read())

    sources = parser.parse()
    for name, source in sources.items():
        print '{}: {}'.format(name, source['Subversion'] if 'Subversion' in source else source['Git'])

if __name__ == "__main__":
    main()
