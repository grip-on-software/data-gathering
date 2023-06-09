# Stubs for github.GitReleaseAsset (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.GithubObject
from typing import Any

class GitReleaseAsset(github.GithubObject.CompletableGithubObject):
    @property
    def url(self): ...
    @property
    def id(self): ...
    @property
    def name(self): ...
    @name.setter
    def name(self, value: Any) -> None: ...
    @property
    def label(self): ...
    @label.setter
    def label(self, value: Any) -> None: ...
    @property
    def content_type(self): ...
    @property
    def state(self): ...
    @property
    def size(self): ...
    @property
    def download_count(self): ...
    @property
    def created_at(self): ...
    @property
    def updated_at(self): ...
    @property
    def browser_download_url(self): ...
    @property
    def uploader(self): ...
    def delete_asset(self): ...
    def update_asset(self, name: Any, label: str = ...): ...
