# Stubs for git.objects.submodule.root (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .base import Submodule, UpdateProgress
from typing import Any, Optional

class RootUpdateProgress(UpdateProgress):
    REMOVE: Any = ...
    PATHCHANGE: Any = ...
    BRANCHCHANGE: Any = ...
    URLCHANGE: Any = ...

class RootModule(Submodule):
    k_root_name: str = ...
    def __init__(self, repo: Any) -> None: ...
    def update(self, recursive: bool = ..., init: bool = ..., to_latest_revision: bool = ..., progress: Optional[Any] = ..., dry_run: bool = ..., force: bool = ..., keep_going: bool = ..., **kwargs: Any): ...
    def module(self): ...
