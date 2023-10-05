#!/usr/bin/env python
"""
Package setup script.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

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

from setuptools import setup, find_packages
from gatherer import __version__

def main() -> None:
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
and Azure DevOps/TFS/VSTS), quality report systems (SonarQube and HQ), 
build automation servers (Jenkins) and reservation systems (Topdesk).''',
          author='Leon Helwerda',
          author_email='l.s.helwerda@liacs.leidenuniv.nl',
          url='https://github.com/grip-on-software/data-gathering',
          license='Apache 2.0',
          packages=find_packages(),
          package_data={'gatherer': ['py.typed']},
          entry_points={},
          include_package_data=True,
          install_requires=[
              # gatherer.config
              'urlmatch',
              # gatherer.jira
              'jira>=2.0.1.0rc1',
              # gatherer.git
              'gitpython>=2.1.8', 'PyGithub>1.40', 'python-gitlab>1.10.0',
              # gatherer.svn
              'svn>=0.3.45',
              # gatherer.request
              'requests', 'requests_ntlm', 'ordered-set',
              # gatherer.database
              'pymonetdb',
              # gatherer.files
              'pyocclient',
              # gatherer.salt
              'bcrypt'
          ],
          python_requires='>=3.6',
          dependency_links=[],
          classifiers=[
              'Development Status :: 3 - Alpha',
              'Environment :: Console',
              'Environment :: Web Environment',
              'Intended Audience :: Developers',
              'Intended Audience :: Information Technology',
              'Topic :: Software Development :: Bug Tracking',
              'Topic :: Software Development :: Build Tools',
              'Topic :: Software Development :: Quality Assurance',
              'Topic :: Software Development :: Version Control :: Git',
              'Topic :: System :: Distributed Computing',
              'Topic :: System :: Monitoring',
              'License :: OSI Approved :: Apache Software License',
              'Programming Language :: Python :: 3',
              'Programming Language :: Python :: 3.6',
              'Programming Language :: Python :: 3.7',
              'Programming Language :: Python :: 3.8'
          ],
          keywords='gros software development process data gathering')

if __name__ == '__main__':
    main()
