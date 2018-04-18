#!/usr/bin/env python
"""
Package setup script.
"""

try:
    from builtins import str
except ImportError:
    pass
try:
    from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
except ImportError:
    from urllib import urlencode
    from urlparse import parse_qs, urlsplit, urlunsplit
from setuptools import setup, find_packages
from gatherer import __version__

def parse_requirements(filename):
    """
    Collect requirement specifications and dependency links from a requirements
    file. Each non-empty line of the file that is not a comment or starts with
    an argument is considered to be a requirement specification. Requirements
    that are actually links (indicated by the presence of a protocol schema)
    provide dependency links, where the egg name is used for the requirement.
    A dependency link has the form of a URL string containing the base version
    control URL plus optional branch/tag, the egg fragment and optionally the
    subdirectory. The egg name is altered to favor the dependency link over
    other sources.

    Returns two lists, respectively containing the requirement specifications
    and the dependency links.
    """

    requirements = []
    links = []
    with open(filename, 'r') as requirements_file:
        for line in requirements_file:
            requirement = line.strip()
            if requirement != '' and not requirement.startswith('#') and \
                not requirement.startswith('-'):
                url_parts = urlsplit(requirement)
                if url_parts.scheme != '':
                    fragment = parse_qs(url_parts.fragment)
                    if 'egg' in fragment:
                        egg = fragment['egg'][0].rpartition('-')
                        requirements.append(egg[0] if egg[0] != '' else egg[-1])

                        fragment['egg'] = '{}-999999'.format(fragment['egg'][0])

                    parsed_fragment = urlencode(fragment, doseq=True)
                    link = urlunsplit(url_parts[:-1] + (parsed_fragment,))
                    links.append(link)
                else:
                    requirements.append(requirement)

    return requirements, links

def main():
    """
    Setup the package.
    """

    requirements, links = parse_requirements('requirements.txt')

    setup(name='gros-gatherer',
          version=__version__,
          description='Software development process data gathering',
          long_description='''Gather data from different sources that are
used by software development teams and projects in a distributed environment,
as part of a pipeline where the gathered data is stored in a database for
analysis purposes. Sources include issue trackers (Jira), version control
systems (Git and Subversion) and associated review systems (GitHub, GitLab,
and Team Foundation Server), quality report systems (SonarQube and HQ), 
build automation servers (Jenkins) and reservation systems (Topdesk).''',
          author='Leon Helwerda',
          author_email='l.s.helwerda@liacs.leidenuniv.nl',
          url='',
          license='',
          packages=find_packages(),
          entry_points={},
          include_package_data=True,
          install_requires=requirements,
          dependency_links=links,
          classifiers=[],
          keywords=[])

if __name__ == '__main__':
    main()
