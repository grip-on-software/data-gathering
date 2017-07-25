"""
Module that handles access to a GitHub-based repository, augmenting the usual
repository version information with pull requests and commit comments.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import str
from .repo import Git_Repository
from ..table import Key_Table, Link_Table
from ..utils import format_date, parse_unicode
from ..version_control.review import Review_System

class GitHub_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by GitHub.
    """

    @property
    def review_tables(self):
        review_tables = super(GitHub_Repository, self).review_tables
        review_fields = self.build_user_fields('reviewer')
        review_tables.update({
            "github_repo": Key_Table('github_repo', 'github_id'),
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypted_fields=review_fields)
        })
        return review_tables

    @property
    def update_tracker_name(self):
        return "github_update"

    @property
    def api(self):
        """
        Retrieve an instance of the GitHub API connection for this source.
        """

        return self._source.github_api

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        versions = super(GitHub_Repository, self).get_data(from_revision,
                                                           to_revision,
                                                           **kwargs)

        self.fill_repo_table(self._source.github_repo)
        for pull_request in self._source.github_repo.get_pulls():
            newer = self.add_pull_request(pull_request)
            if newer:
                for issue_comment in pull_request.get_issue_comments():
                    self.add_issue_comment(issue_comment, pull_request.number)
                for review_comment in pull_request.get_review_comments():
                    self.add_commit_comment(review_comment, pull_request.number)
                for review in pull_request.get_reviews():
                    self.add_review(review, pull_request.number)

        for issue in self._source.github_repo.get_issues():
            newer = self.add_issue(issue)
            if newer:
                for issue_comment in issue.get_comments():
                    self.add_issue_comment(issue_comment, issue.number)

        return versions

    def fill_repo_table(self, repo):
        """
        Add the repository data from a GitHub API Repository object `repo`
        to the table for GitHub repositories.
        """

        if repo.description is not None:
            description = parse_unicode(repo.description)
        else:
            description = str(0)

        if repo.private:
            private = str(1)
        else:
            private = str(0)

        if repo.fork:
            forked = str(1)
        else:
            forked = str(0)

        self._tables["github_repo"].append({
            "repo_name": str(self._repo_name),
            "github_id": str(repo.id),
            "description": description,
            "create_time": format_date(repo.created_at),
            "private": private,
            "forked": forked,
            "star_count": str(repo.stargazers_count),
            "watch_count": str(repo.watchers_count)
        })

    def add_pull_request(self, pull_request):
        """
        Add a pull request described by its GitHub API response object to the
        merge requests table. Returns whether the pull request is updated more
        recently than the update tracker date.
        """

        pass

    def add_issue(self, issue):
        """
        Add an issue described by its GitHub API response object to the repo
        issues table. Returns whether the issue is updated more recently than
        the update tracker date.
        """

        pass

    def add_issue_comment(self, note, issue_id):
        """
        Add an issue or normal pull request comment described by its GitHub API
        response object to the repo merge request notes table.
        """

        pass

    def add_commit_comment(self, note, request_id=None):
        """
        Add a commit comment or pull request review comment described by its
        GitHub API response object to the commit comments table.
        """

        pass

    def add_review(self, review, request_id):
        """
        Add a pull request review described by its GitHub API response object
        to the merge request reviews table.
        """

        pass
