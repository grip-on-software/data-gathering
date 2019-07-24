# Stubs for github.NamedUser (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .PaginatedList import PaginatedList
from .Repository import Repository
import github.Event
from typing import Any

class NamedUser(github.GithubObject.CompletableGithubObject):
    @property
    def node_id(self): ...
    def __hash__(self): ...
    def __eq__(self, other: Any): ...
    @property
    def avatar_url(self): ...
    @property
    def bio(self): ...
    @property
    def blog(self): ...
    @property
    def collaborators(self): ...
    @property
    def company(self): ...
    @property
    def contributions(self): ...
    @property
    def created_at(self): ...
    @property
    def disk_usage(self): ...
    @property
    def email(self): ...
    @property
    def events_url(self): ...
    @property
    def followers(self): ...
    @property
    def followers_url(self): ...
    @property
    def following(self): ...
    @property
    def following_url(self): ...
    @property
    def gists_url(self): ...
    @property
    def gravatar_id(self): ...
    @property
    def hireable(self): ...
    @property
    def html_url(self): ...
    @property
    def id(self): ...
    @property
    def invitation_teams_url(self): ...
    @property
    def inviter(self): ...
    @property
    def location(self): ...
    @property
    def login(self) -> str: ...
    @property
    def name(self): ...
    @property
    def organizations_url(self): ...
    @property
    def owned_private_repos(self): ...
    @property
    def permissions(self): ...
    @property
    def plan(self): ...
    @property
    def private_gists(self): ...
    @property
    def public_gists(self): ...
    @property
    def public_repos(self): ...
    @property
    def received_events_url(self): ...
    @property
    def repos_url(self): ...
    @property
    def role(self): ...
    @property
    def site_admin(self): ...
    @property
    def starred_url(self): ...
    @property
    def subscriptions_url(self): ...
    @property
    def suspended_at(self): ...
    @property
    def team_count(self): ...
    @property
    def total_private_repos(self): ...
    @property
    def type(self) -> str: ...
    @property
    def updated_at(self): ...
    @property
    def url(self): ...
    def get_events(self): ...
    def get_followers(self): ...
    def get_following(self): ...
    def get_gists(self, since: Any = ...): ...
    def get_keys(self): ...
    def get_orgs(self): ...
    def get_public_events(self): ...
    def get_public_received_events(self): ...
    def get_received_events(self): ...
    def get_repo(self, name: Any): ...
    def get_repos(self, type: str = ..., sort: str = ..., direction: str = ...) -> PaginatedList[Repository]: ...
    def get_starred(self): ...
    def get_subscriptions(self): ...
    def get_watched(self): ...
    def has_in_following(self, following: Any): ...