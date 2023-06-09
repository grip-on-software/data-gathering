# Stubs for github.Organization (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .PaginatedList import PaginatedList
from .Team import Team
import github.NamedUser
from typing import Any

class Organization(github.GithubObject.CompletableGithubObject):
    @property
    def avatar_url(self): ...
    @property
    def billing_email(self): ...
    @property
    def blog(self): ...
    @property
    def collaborators(self): ...
    @property
    def company(self): ...
    @property
    def created_at(self): ...
    @property
    def description(self): ...
    @property
    def disk_usage(self): ...
    @property
    def email(self): ...
    @property
    def events_url(self): ...
    @property
    def followers(self): ...
    @property
    def following(self): ...
    @property
    def gravatar_id(self): ...
    @property
    def html_url(self): ...
    @property
    def id(self): ...
    @property
    def location(self): ...
    @property
    def login(self): ...
    @property
    def members_url(self): ...
    @property
    def name(self): ...
    @property
    def owned_private_repos(self): ...
    @property
    def plan(self): ...
    @property
    def private_gists(self): ...
    @property
    def public_gists(self): ...
    @property
    def public_members_url(self): ...
    @property
    def public_repos(self): ...
    @property
    def repos_url(self): ...
    @property
    def total_private_repos(self): ...
    @property
    def two_factor_requirement_enabled(self): ...
    @property
    def type(self): ...
    @property
    def updated_at(self): ...
    @property
    def url(self): ...
    def add_to_members(self, member: Any, role: Any = ...) -> None: ...
    def add_to_public_members(self, public_member: Any) -> None: ...
    def create_fork(self, repo: Any): ...
    def create_hook(self, name: Any, config: Any, events: Any = ..., active: Any = ...): ...
    def create_repo(self, name: Any, description: Any = ..., homepage: Any = ..., private: Any = ..., has_issues: Any = ..., has_wiki: Any = ..., has_downloads: Any = ..., has_projects: Any = ..., team_id: Any = ..., auto_init: Any = ..., license_template: Any = ..., gitignore_template: Any = ..., allow_squash_merge: Any = ..., allow_merge_commit: Any = ..., allow_rebase_merge: Any = ...): ...
    def create_team(self, name: Any, repo_names: Any = ..., permission: Any = ..., privacy: Any = ..., description: Any = ...): ...
    def delete_hook(self, id: Any) -> None: ...
    def edit(self, billing_email: Any = ..., blog: Any = ..., company: Any = ..., description: Any = ..., email: Any = ..., location: Any = ..., name: Any = ...) -> None: ...
    def edit_hook(self, id: Any, name: Any, config: Any, events: Any = ..., active: Any = ...): ...
    def get_events(self): ...
    def get_hook(self, id: Any): ...
    def get_hooks(self): ...
    def get_issues(self, filter: Any = ..., state: Any = ..., labels: Any = ..., sort: Any = ..., direction: Any = ..., since: Any = ...): ...
    def get_members(self, filter_: Any = ..., role: Any = ...): ...
    def get_projects(self, state: Any = ...): ...
    def get_public_members(self): ...
    def get_outside_collaborators(self, filter_: Any = ...): ...
    def remove_outside_collaborator(self, collaborator: Any) -> None: ...
    def convert_to_outside_collaborator(self, member: Any) -> None: ...
    def get_repo(self, name: Any): ...
    def get_repos(self, type: Any = ..., sort: Any = ..., direction: Any = ...): ...
    def get_team(self, id: Any): ...
    def get_team_by_slug(self, slug: Any): ...
    def get_teams(self) -> PaginatedList[Team]: ...
    def invitations(self): ...
    def invite_user(self, user: Any = ..., email: Any = ..., role: Any = ..., teams: Any = ...) -> None: ...
    def has_in_members(self, member: Any): ...
    def has_in_public_members(self, public_member: Any): ...
    def remove_from_membership(self, member: Any) -> None: ...
    def remove_from_members(self, member: Any) -> None: ...
    def remove_from_public_members(self, public_member: Any) -> None: ...
    def create_migration(self, repos: Any, lock_repositories: Any = ..., exclude_attachments: Any = ...): ...
    def get_migrations(self): ...
