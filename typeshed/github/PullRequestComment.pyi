# Stubs for github.PullRequestComment (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from datetime import datetime
from .GithubObject import CompletableGithubObject
from .NamedUser import NamedUser
from typing import Any, Optional

class PullRequestComment(CompletableGithubObject):
    @property
    def body(self) -> str: ...
    @property
    def commit_id(self): ...
    @property
    def created_at(self) -> datetime: ...
    @property
    def diff_hunk(self) -> str: ...
    @property
    def id(self) -> int: ...
    @property
    def in_reply_to_id(self): ...
    @property
    def original_commit_id(self): ...
    @property
    def original_position(self) -> int: ...
    @property
    def path(self): ...
    @property
    def position(self) -> Optional[int]: ...
    @property
    def pull_request_url(self): ...
    @property
    def updated_at(self) -> datetime: ...
    @property
    def url(self): ...
    @property
    def html_url(self): ...
    @property
    def user(self) -> NamedUser: ...
    def delete(self) -> None: ...
    def edit(self, body: Any) -> None: ...
    def get_reactions(self): ...
    def create_reaction(self, reaction_type: Any): ...