# Stubs for github.Installation (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.Notification
from typing import Any

INTEGRATION_PREVIEW_HEADERS: Any

class Installation(github.GithubObject.NonCompletableGithubObject):
    @property
    def id(self): ...
    def get_repos(self): ...