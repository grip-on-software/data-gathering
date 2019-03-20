#!/usr/bin/env python
"""
Package setup script.
"""

from setuptools import setup, find_packages
from gatherer import __version__

def main():
    """
    Setup the package.
    """

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
              # gatherer.config
              'urlmatch',
              # gatherer.git
              'gitpython', 'PyGithub', 'python-gitlab',
              # gatherer.svn
              'svn',
              # gatherrr.request
              'requests', 'requests_ntlm', 'ordered-set',
              # gatherer.project_definition
              'mock',
              # gatherer.database
              'pymonetdb',
              # gatherer.files
              'pyocclient',
              # gatherer.salt
              'bcrypt'
          ],
          dependency_links=[],
          classifiers=[],
          keywords=[])

if __name__ == '__main__':
    main()
