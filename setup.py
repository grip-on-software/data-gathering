#!/usr/bin/env python
"""
Package setup script.
"""

from builtins import str
from pip.download import PipSession
from pip.req import parse_requirements
from setuptools import setup, find_packages
from gatherer import __version__

def build_dependency_link(requirement):
    """
    Create a dependency link of the form of a URL string containing only
    the version control URL and the egg fragment.
    """

    link = requirement.link
    return link.url_without_fragment + '#egg=' + link.egg_fragment

def main():
    """
    Setup the package.
    """

    requirements = list(parse_requirements('requirements.txt',
                                           session=PipSession()))

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
          install_requires=[
              str(requirement.req) for requirement in requirements
              if requirement.match_markers()
          ],
          dependency_links=[
              build_dependency_link(requirement) for requirement in requirements
              if requirement.link is not None
          ],
          classifiers=[],
          keywords=[])

if __name__ == '__main__':
    main()
