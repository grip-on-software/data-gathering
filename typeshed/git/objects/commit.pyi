# Stubs for git.objects.commit (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from datetime import datetime
from . import base
from .util import Serializable, Traversable
from git.diff import Diffable
from git.objects.tree import Tree
from git.util import Actor, Iterable, Stats
from typing import Any, Optional, Tuple

class Commit(base.Object, Iterable, Diffable, Traversable, Serializable):
    env_author_date: str = ...
    env_committer_date: str = ...
    conf_encoding: str = ...
    default_encoding: str = ...
    type: str = ...
    tree: Tree = ...
    author: Actor = ...
    authored_date: Any = ...
    author_tz_offset: Any = ...
    committer: Any = ...
    committed_date: Any = ...
    committer_tz_offset: Any = ...
    message: str = ...
    parents: Tuple['Commit'] = ...
    encoding: Any = ...
    gpgsig: Any = ...
    hexsha: str = ...
    size: int = ...
    def __init__(self, repo: Any, binsha: Any, tree: Optional[Any] = ..., author: Optional[Any] = ..., authored_date: Optional[Any] = ..., author_tz_offset: Optional[Any] = ..., committer: Optional[Any] = ..., committed_date: Optional[Any] = ..., committer_tz_offset: Optional[Any] = ..., message: Optional[Any] = ..., parents: Optional[Any] = ..., encoding: Optional[Any] = ..., gpgsig: Optional[Any] = ...) -> None: ...
    @property
    def authored_datetime(self) -> datetime: ...
    @property
    def committed_datetime(self) -> datetime: ...
    @property
    def summary(self): ...
    def count(self, paths: str = ..., **kwargs: Any): ...
    @property
    def name_rev(self): ...
    @classmethod
    def iter_items(cls, repo: Any, *args: Any, **kwargs: Any): ...
    def iter_parents(self, paths: str = ..., **kwargs: Any): ...
    @property
    def stats(self) -> Stats: ...
    @classmethod
    def create_from_tree(cls, repo: Any, tree: Any, message: Any, parent_commits: Optional[Any] = ..., head: bool = ..., author: Optional[Any] = ..., committer: Optional[Any] = ..., author_date: Optional[Any] = ..., commit_date: Optional[Any] = ...): ...
