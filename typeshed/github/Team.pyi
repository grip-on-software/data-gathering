# Stubs for github.Team (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .PaginatedList import PaginatedList
from .Repository import Repository
import github.Organization
from typing import Any

class Team(github.GithubObject.CompletableGithubObject):
    @property
    def id(self): ...
    @property
    def members_count(self): ...
    @property
    def members_url(self): ...
    @property
    def name(self): ...
    @property
    def description(self): ...
    @property
    def permission(self): ...
    @property
    def repos_count(self): ...
    @property
    def repositories_url(self): ...
    @property
    def slug(self) -> str: ...
    @property
    def url(self): ...
    @property
    def organization(self): ...
    @property
    def privacy(self): ...
    def add_to_members(self, member: Any) -> None: ...
    def add_membership(self, member: Any, role: Any = ...) -> None: ...
    def add_to_repos(self, repo: Any) -> None: ...
    def set_repo_permission(self, repo: Any, permission: Any) -> None: ...
    def delete(self) -> None: ...
    def edit(self, name: Any, description: Any = ..., permission: Any = ..., privacy: Any = ...) -> None: ...
    def get_members(self, role: Any = ...): ...
    def get_repos(self) -> PaginatedList[Repository]: ...
    def invitations(self): ...
    def has_in_members(self, member: Any): ...
    def has_in_repos(self, repo: Any): ...
    def remove_membership(self, member: Any) -> None: ...
    def remove_from_members(self, member: Any) -> None: ...
    def remove_from_repos(self, repo: Any) -> None: ...