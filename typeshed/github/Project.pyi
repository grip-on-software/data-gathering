# Stubs for github.Project (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.ProjectColumn
from typing import Any

class Project(github.GithubObject.CompletableGithubObject):
    @property
    def body(self): ...
    @property
    def columns_url(self): ...
    @property
    def created_at(self): ...
    @property
    def creator(self): ...
    @property
    def html_url(self): ...
    @property
    def id(self): ...
    @property
    def name(self): ...
    @property
    def node_id(self): ...
    @property
    def number(self): ...
    @property
    def owner_url(self): ...
    @property
    def state(self): ...
    @property
    def updated_at(self): ...
    @property
    def url(self): ...
    def get_columns(self): ...
    def create_column(self, name: Any): ...
