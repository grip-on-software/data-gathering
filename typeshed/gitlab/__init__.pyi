# Stubs for gitlab (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from gitlab.const import *
from gitlab.exceptions import *
from gitlab.v4.objects import CurrentUser, GroupManager, ProjectManager
from typing import Any, Iterator, Optional, Sized, Tuple, TypeVar

T = TypeVar('T')

__title__: str
__email__: str
__license__: str
__copyright__: str
REDIRECT_MSG: str

class Gitlab:
    timeout: Optional[float] = ...
    headers: Any = ...
    email: Any = ...
    password: Any = ...
    ssl_verify: Any = ...
    private_token: Any = ...
    http_username: Any = ...
    http_password: Any = ...
    oauth_token: Any = ...
    session: Any = ...
    per_page: Any = ...
    broadcastmessages: Any = ...
    deploykeys: Any = ...
    geonodes: Any = ...
    gitlabciymls: Any = ...
    gitignores: Any = ...
    groups: GroupManager = ...
    hooks: Any = ...
    issues: Any = ...
    ldapgroups: Any = ...
    licenses: Any = ...
    namespaces: Any = ...
    mergerequests: Any = ...
    notificationsettings: Any = ...
    projects: ProjectManager = ...
    runners: Any = ...
    settings: Any = ...
    sidekiq: Any = ...
    snippets: Any = ...
    users: Any = ...
    todos: Any = ...
    dockerfiles: Any = ...
    events: Any = ...
    features: Any = ...
    pagesdomains: Any = ...
    user_activities: Any = ...
    user: CurrentUser = ...
    def __init__(self, url: Any, private_token: Optional[Any] = ..., oauth_token: Optional[Any] = ..., email: Optional[Any] = ..., password: Optional[Any] = ..., ssl_verify: bool = ..., http_username: Optional[Any] = ..., http_password: Optional[Any] = ..., timeout: Optional[Any] = ..., api_version: str = ..., session: Optional[Any] = ..., per_page: Optional[Any] = ...) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *args: Any) -> None: ...
    @property
    def url(self): ...
    @property
    def api_url(self): ...
    @property
    def api_version(self): ...
    @classmethod
    def from_config(cls, gitlab_id: Optional[Any] = ..., config_files: Optional[Any] = ...): ...
    def auth(self) -> None: ...
    def version(self) -> Tuple[str, str]: ...
    def lint(self, content: Any, **kwargs: Any): ...
    def markdown(self, text: Any, gfm: bool = ..., project: Optional[Any] = ..., **kwargs: Any): ...
    def get_license(self, **kwargs: Any): ...
    def set_license(self, license: Any, **kwargs: Any): ...
    def enable_debug(self) -> None: ...
    def http_request(self, verb: Any, path: Any, query_data: Any = ..., post_data: Optional[Any] = ..., streamed: bool = ..., files: Optional[Any] = ..., **kwargs: Any): ...
    def http_get(self, path: Any, query_data: Any = ..., streamed: bool = ..., raw: bool = ..., **kwargs: Any): ...
    def http_list(self, path: Any, query_data: Any = ..., as_list: Optional[Any] = ..., **kwargs: Any): ...
    def http_post(self, path: Any, query_data: Any = ..., post_data: Any = ..., files: Optional[Any] = ..., **kwargs: Any): ...
    def http_put(self, path: Any, query_data: Any = ..., post_data: Any = ..., files: Optional[Any] = ..., **kwargs: Any): ...
    def http_delete(self, path: Any, **kwargs: Any): ...
    def search(self, scope: Any, search: Any, **kwargs: Any): ...

class GitlabList(Iterator[T], Sized):
    def __init__(self, gl: Any, url: Any, query_data: Any, get_next: bool = ..., **kwargs: Any) -> None: ...
    @property
    def current_page(self) -> int: ...
    @property
    def prev_page(self) -> int: ...
    @property
    def next_page(self) -> int: ...
    @property
    def per_page(self) -> int: ...
    @property
    def total_pages(self) -> int: ...
    @property
    def total(self) -> int: ...
    def __iter__(self) -> Iterator[T]: ...
    def __len__(self) -> int: ...
    def __next__(self) -> T: ...
    def next(self) -> T: ...
