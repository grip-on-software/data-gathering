# Stubs for github.GithubObject (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Dict, Optional

atLeastPython3: Any

class _NotSetType:
    value: Any = ...

NotSet: Any

class _ValuedAttribute:
    value: Any = ...
    def __init__(self, value: Any) -> None: ...

class _BadAttribute:
    def __init__(self, value: Any, expectedType: Any, exception: Optional[Any] = ...) -> None: ...
    @property
    def value(self) -> None: ...

class GithubObject:
    CHECK_AFTER_INIT_FLAG: bool = ...
    @classmethod
    def setCheckAfterInitFlag(cls, flag: Any) -> None: ...
    def __init__(self, requester: Any, headers: Any, attributes: Any, completed: Any) -> None: ...
    @property
    def raw_data(self) -> Dict[str, Any]: ...
    @property
    def raw_headers(self): ...
    @property
    def etag(self): ...
    @property
    def last_modified(self): ...
    def get__repr__(self, params: Any): ...

class NonCompletableGithubObject(GithubObject): ...

class CompletableGithubObject(GithubObject):
    def __init__(self, requester: Any, headers: Any, attributes: Any, completed: Any) -> None: ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
    def update(self): ...
