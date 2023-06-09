# Stubs for git.remote (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from git.util import Iterable, IterableList, LazyMixin, RemoteProgress as RemoteProgress
from typing import Any, Callable, List, Optional, Union

Progress = Union[Callable[[int, int, Optional[int], str], None], RemoteProgress]
Refspec = Union[str, List[str]]

class PushInfo:
    NEW_TAG: Any = ...
    NEW_HEAD: Any = ...
    NO_MATCH: Any = ...
    REJECTED: Any = ...
    REMOTE_REJECTED: Any = ...
    REMOTE_FAILURE: Any = ...
    DELETED: Any = ...
    FORCED_UPDATE: Any = ...
    FAST_FORWARD: Any = ...
    UP_TO_DATE: Any = ...
    ERROR: Any = ...
    flags: Any = ...
    local_ref: Any = ...
    remote_ref_string: Any = ...
    summary: Any = ...
    def __init__(self, flags: Any, local_ref: Any, remote_ref_string: Any, remote: Any, old_commit: Optional[Any] = ..., summary: str = ...) -> None: ...
    @property
    def old_commit(self): ...
    @property
    def remote_ref(self): ...

class FetchInfo:
    NEW_TAG: Any = ...
    NEW_HEAD: Any = ...
    HEAD_UPTODATE: Any = ...
    TAG_UPDATE: Any = ...
    REJECTED: Any = ...
    FORCED_UPDATE: Any = ...
    FAST_FORWARD: Any = ...
    ERROR: Any = ...
    @classmethod
    def refresh(cls): ...
    ref: Any = ...
    flags: Any = ...
    note: Any = ...
    old_commit: Any = ...
    remote_ref_path: Any = ...
    def __init__(self, ref: Any, flags: Any, note: str = ..., old_commit: Optional[Any] = ..., remote_ref_path: Optional[Any] = ...) -> None: ...
    @property
    def name(self): ...
    @property
    def commit(self): ...

class Remote(LazyMixin, Iterable):
    repo: Any = ...
    name: Any = ...
    def __init__(self, repo: Any, name: Any) -> None: ...
    def __getattr__(self, attr: Any): ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
    def __hash__(self): ...
    def exists(self): ...
    @classmethod
    def iter_items(cls, repo: Any, *args: Any, **kwargs: Any) -> None: ...
    def set_url(self, new_url: Any, old_url: Optional[Any] = ..., **kwargs: Any): ...
    def add_url(self, url: Any, **kwargs: Any): ...
    def delete_url(self, url: Any, **kwargs: Any): ...
    @property
    def urls(self) -> None: ...
    @property
    def refs(self): ...
    @property
    def stale_refs(self): ...
    @classmethod
    def create(cls, repo: Any, name: Any, url: Any, **kwargs: Any): ...
    add: Any = ...
    @classmethod
    def remove(cls, repo: Any, name: Any): ...
    rm: Any = ...
    def rename(self, new_name: Any): ...
    def update(self, **kwargs: Any): ...
    def fetch(self, refspec: Optional[Refspec] = ..., progress: Optional[Progress] = ..., **kwargs: Any) -> IterableList[FetchInfo]: ...
    def pull(self, refspec: Optional[Refspec] = ..., progress: Optional[Progress] = ..., **kwargs: Any) -> IterableList[FetchInfo]: ...
    def push(self, refspec: Optional[Refspec] = ..., progress: Optional[Progress] = ..., **kwargs: Any) -> IterableList[PushInfo]: ...
    @property
    def config_reader(self): ...
    @property
    def config_writer(self): ...
