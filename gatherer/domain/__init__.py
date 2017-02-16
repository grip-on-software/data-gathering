"""
Package containing domain modules for the projects that have specifications
about what kind of data we can gather from them.
"""

from .project import Project
from .source import Source

__all__ = ["Project", "Source"]
