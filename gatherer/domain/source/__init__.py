"""
Data gathering package for source domain objects.

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

from .types import Source
from .svn import Subversion
from .git import Git
from .github import GitHub
from .gitlab import GitLab
from .tfs import TFS, TFVC
from .history import History
from .metric_options import Metric_Options
from .quality_time import Quality_Time
from .jenkins import Jenkins
from .jira import Jira
from .sonar import Sonar
from .controller import Controller

__all__ = [
    # Main classes
    "Source",
    # Version control system classes
    "Subversion", "Git", "GitHub", "GitLab", "TFS", "TFVC",
    # Quality metrics
    "History", "Metric_Options", "Quality_Time",
    # Other sources
    "Jenkins", "Jira", "Controller"
]
