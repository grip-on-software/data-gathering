# Stubs for svn.remote (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import svn.common
from typing import Any, Optional

class RemoteClient(svn.common.CommonClient):
    def __init__(self, url: Any, *args: Any, **kwargs: Any) -> None: ...
    def checkout(self, path: Any, revision: Optional[Any] = ...) -> None: ...
