# Stubs for github.Tag (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.Commit

class Tag(github.GithubObject.NonCompletableGithubObject):
    @property
    def commit(self): ...
    @property
    def name(self): ...
    @property
    def tarball_url(self): ...
    @property
    def zipball_url(self): ...