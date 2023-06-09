# Stubs for git.repo.fun (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any

def touch(filename: Any): ...
def is_git_dir(d: Any): ...
def find_worktree_git_dir(dotgit: Any): ...
def find_submodule_git_dir(d: Any): ...
def short_to_long(odb: Any, hexsha: Any): ...
def name_to_object(repo: Any, name: Any, return_ref: bool = ...): ...
def deref_tag(tag: Any): ...
def to_commit(obj: Any): ...
def rev_parse(repo: Any, rev: Any): ...
