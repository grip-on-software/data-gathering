# Stubs for github.RequiredPullRequestReviews (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import github.Team

class RequiredPullRequestReviews(github.GithubObject.CompletableGithubObject):
    @property
    def dismiss_stale_reviews(self): ...
    @property
    def require_code_owner_reviews(self): ...
    @property
    def required_approving_review_count(self): ...
    @property
    def url(self): ...
    @property
    def dismissal_users(self): ...
    @property
    def dismissal_teams(self): ...