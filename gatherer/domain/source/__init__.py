"""
Data gathering package for source domain objects.
"""

from .types import Source
from .svn import Subversion
from .git import Git
from .github import GitHub
from .gitlab import GitLab
from .tfs import TFS
from .history import History
from .jenkins import Jenkins
from .jira import Jira
from .controller import Controller

__all__ = [
    # Main classes
    "Source",
    # Version control system classes
    "Subversion", "Git", "GitHub", "GitLab", "TFS",
    # Other sources
    "History", "Jenkins", "Jira", "Controller"
]
