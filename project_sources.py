"""
Script to parse current project definitions and extract metric sources from
the products and components.
"""

import argparse
import ConfigParser
import urlparse

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

def parse_sources(sources):
    """
    Read a list of source repositories, clone or update them if necessary,
    and output data that can be used by other gatherer scripts.
    """

    credentials = ConfigParser.RawConfigParser()
    credentials.read("credentials.cfg")

    urls = set()
    for name, source in sources.items():
        url = source['Subversion'] if 'Subversion' in source else source['Git']
        print '{}: {} ({})'.format(name, url, 'Subversion' if 'Subversion' in source else 'Git')
        parts = urlparse.urlsplit(url)
        host = parts.netloc
        if credentials.has_section(host):
            username = credentials.get(host, 'username')
            password = credentials.get(host, 'password')
            if credentials.has_option(host, 'host'):
                host = credentials.get(host, 'host')

            auth = '{0}:{1}'.format(username, password)
            host = auth + '@' + host

        url = urlparse.urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        urls.add(url)

    print urls

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
        print 'No project sources available for {}, skipping.'.format(project_key)
        return

    filename = args.repo + '/' + project_name + '/project_definition.py'
    parser = Sources_Parser(args.repo)

    with open(filename, 'r') as definition_file:
        parser.load_definition(definition_file.read())

    sources = parser.parse()
    parse_sources(sources)

if __name__ == "__main__":
    main()
