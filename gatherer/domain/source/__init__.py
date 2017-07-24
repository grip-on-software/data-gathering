"""
Data gathering package for source domain objects.
"""

from .types import Source
from .svn import Subversion
from .git import Git
from .github import GitHub
from .gitlab import GitLab
from .tfs import TFS

__all__ = ["Source", "Subversion", "Git", "GitHub", "GitLab", "TFS"]
