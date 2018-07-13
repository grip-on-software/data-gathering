"""
Data gathering package for source domain objects.
"""

from .types import Source
from .svn import Subversion
from .git import Git
from .github import GitHub
from .gitlab import GitLab
from .tfs import TFS, TFVC
from .history import History
from .metric_options import Metric_Options
from .jenkins import Jenkins
from .jira import Jira
from .controller import Controller

__all__ = [
    # Main classes
    "Source",
    # Version control system classes
    "Subversion", "Git", "GitHub", "GitLab", "TFS", "TFVC",
    # Quality metrics
    "History", "Metric_Options",
    # Other sources
    "Jenkins", "Jira", "Controller"
]
