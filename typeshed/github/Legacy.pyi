# Stubs for github.Legacy (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.PaginatedList
from typing import Any

class PaginatedList(github.PaginatedList.PaginatedListBase):
    def __init__(self, url: Any, args: Any, requester: Any, key: Any, convert: Any, contentClass: Any) -> None: ...
    def get_page(self, page: Any): ...

def convertUser(attributes: Any): ...
def convertRepo(attributes: Any): ...
def convertIssue(attributes: Any): ...
