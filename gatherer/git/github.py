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
import re
from .repo import Git_Repository
from ..table import Key_Table, Link_Table
from ..utils import format_date, parse_unicode, convert_utc_datetime
from ..version_control.review import Review_System

class GitHub_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by GitHub.
    """

    UPVOTE = 'APPROVED'
    DOWNVOTE = 'CHANGES_REQUESTED'

    @property
    def review_tables(self):
        review_tables = super(GitHub_Repository, self).review_tables
        author = self.build_user_fields('author')
        assignee = self.build_user_fields('assignee')
        reviewer = self.build_user_fields('reviewer')
        review_tables.update({
            "github_repo": Key_Table('github_repo', 'github_id'),
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypted_fields=reviewer),
            "github_issue": Key_Table('github_issue', 'issue_id',
                                      encrypted_fields=author + assignee),
            "github_issue_note": Link_Table('github_issue_note',
                                            ('issue_id', 'note_id'),
                                            encrypted_fields=author)
        })
        return review_tables

    @property
    def update_tracker_name(self):
        return "github_update"

    @property
    def null_timestamp(self):
        # The datetime strftime() methods require year >= 1900.
        # This is used in get_data to retrieve API data since a given date.
        # All API responses have updated dates that stem from GitHub itself
        # and can thus not be earlier than GitHub's foundation.
        return "1900-01-01 01:01:01"

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
        for pull_request in self._source.github_repo.get_pulls(state='all'):
            newer, reviews = self.add_pull_request(pull_request)
            if newer:
                for issue_comment in pull_request.get_issue_comments():
                    self.add_pull_comment(issue_comment, pull_request.number)
                for review_comment in pull_request.get_review_comments():
                    self.add_commit_comment(review_comment, pull_request.number)
                for review in reviews:
                    self.add_review(review, pull_request.number)

        since = convert_utc_datetime(self.tracker_date)
        for issue in self._source.github_repo.get_issues(state='all',
                                                         since=since):
            newer = self.add_issue(issue)
            if newer:
                for issue_comment in issue.get_comments(since=since):
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

    @staticmethod
    def _get_username(part):
        if part is None:
            return str(0)

        return parse_unicode(part.login)

    def _format_issue(self, issue):
        author_username = self._get_username(issue.user)
        assignee_username = self._get_username(issue.assignee)
        return {
            'repo_name': str(self._repo_name),
            'issue_id': str(issue.number),
            'title': parse_unicode(issue.title),
            'description': parse_unicode(issue.body),
            'status': issue.state,
            'author': author_username,
            'author_username': author_username,
            'assignee': assignee_username,
            'assignee_username': assignee_username,
            'created_at': format_date(issue.created_at),
            'updated_at': format_date(issue.updated_at)
        }

    def add_pull_request(self, pull_request):
        """
        Add a pull request described by its GitHub API response object to the
        merge requests table. Returns whether the pull request is updated more
        recently than the update tracker date and an iterable of the reviews
        associated with the pull request.
        """

        if not self._is_newer(pull_request.updated_at):
            return False, []

        reviews = pull_request.get_reviews()
        upvotes = len([1 for review in reviews if review.state == self.UPVOTE])
        downvotes = len([
            1 for review in reviews if review.state == self.DOWNVOTE
        ])

        request = self._format_issue(pull_request)
        request.update({
            'source_branch': pull_request.head.ref,
            'target_branch': pull_request.base.ref,
            'upvotes': str(upvotes),
            'downvotes': str(downvotes)
        })
        self._tables["merge_request"].append(request)

        return True, reviews

    def add_issue(self, issue):
        """
        Add an issue described by its GitHub API response object to the repo
        issues table. Returns whether the issue is updated more recently than
        the update tracker date.
        """

        if not self._is_newer(issue.updated_at):
            return False

        issue_row = self._format_issue(issue)
        issue_row.update({
            'labels': len(issue.labels),
            'closed_at': format_date(issue.closed_at),
            'closed_by': self._get_username(issue.closed_by)
        })
        self._tables["github_issue"].append(issue_row)

        return True

    def _format_note(self, comment):
        author = self._get_username(comment.user)
        return {
            'repo_name': str(self._repo_name),
            'note_id': comment.id,
            'author': author,
            'author_username': author,
            'comment': parse_unicode(comment.body),
            'created_at': format_date(comment.created_at),
            'updated_at': format_date(comment.updated_at)
        }

    def add_issue_comment(self, comment, issue_id):
        """
        Add an issue comment described by its GitHub API response object to the
        issue notes table. Returns whether the issue comment is updated more
        recently than the update tracker date.
        """

        if not self._is_newer(comment.updated_at):
            return False

        note = self._format_note(comment)
        note['issue_id'] = issue_id
        self._tables["github_issue_note"].append(note)

        return True

    def add_pull_comment(self, comment, request_id):
        """
        Add a normal pull request comment described by its GitHub API response
        object to the repo merge request notes table. Returns whether the pull
        request comment is updated more recently than the update tracker date.
        """

        if not self._is_newer(comment.updated_at):
            return False

        note = self._format_note(comment)
        note.update({
            'thread_id': str(0),
            'parent_id': str(0),
            'merge_request_id': request_id
        })

        self._tables["merge_request_note"].append(note)

        return True

    def add_commit_comment(self, comment, request_id=0):
        """
        Add a commit comment or pull request review comment described by its
        GitHub API response object to the commit comments table. Returns
        whether the issue is updated more recently than the update tracker date.
        """

        if not self._is_newer(comment.updated_at):
            return False

        note = self._format_note(comment)
        if comment.position is None:
            position = str(comment.original_position)
        else:
            position = str(comment.position)

        if comment.diff_hunk is not None and comment.diff_hunk.startswith('@@'):
            lines = comment.diff_hunk.split('\n')
            match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', lines[0])
            if match:
                line = int(match.group(3))
            else:
                line = 0

            end_line = line + position
            if lines[position].startswith('-'):
                line_type = 'old'
            elif lines[position].startswith('+'):
                line_type = 'new'
            else:
                line_type = 'context'
        else:
            line = position
            end_line = position

        note.update({
            'thread_id': str(0),
            'parent_id': str(0),
            'merge_request_id': str(request_id),
            'created_date': note['created_at'],
            'updated_date': note['updated_at'],
            'file': comment.path,
            'line': line,
            'end_line': end_line,
            'line_type': line_type,
            'commit_id': comment.commit_id
        })
        del note['created_at']
        del note['updated_at']

        self._tables["commit_comment"].append(note)

        return True

    def add_review(self, review, request_id):
        """
        Add a pull request review described by its GitHub API response object
        to the merge request reviews table.
        """

        reviewer = self._get_username(review.user)
        if review.state == self.UPVOTE:
            vote = 1
        elif review.state == self.DOWNVOTE:
            vote = -1
        else:
            vote = 0

        self._tables["merge_request_review"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': request_id,
            'reviewer': reviewer,
            'reviewer_name': reviewer,
            'vote': str(vote)
        })
