#!/usr/bin/env python
"""
Package setup script.
"""

from setuptools import setup, find_packages
from gatherer import __version__

setup(name='gros-gatherer',
      version=__version__,
      description='Software development process data gathering',
      long_description='''Gather data from different sources that are used by
software development teams and projects in a distributed environment, as part
of a pipeline where the gathered data is stored in a database for analysis
purposes. Sources include issue trackers (Jira), version control systems
(Git and Subversion) and associated review systems (GitHub, GitLab, and
Team Foundation Server), quality report systems (SonarQube and HQ), 
build automation servers (Jenkins) and reservation systems (Topdesk).''',
      author='Leon Helwerda',
      author_email='l.s.helwerda@liacs.leidenuniv.nl',
      url='',
      license='',
      packages=find_packages(),
      entry_points={},
      include_package_data=True,
      install_requires=[],
      classifiers=[],
      keywords=[])
