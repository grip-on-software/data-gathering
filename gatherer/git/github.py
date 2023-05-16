"""
Module that handles access to a GitHub-based repository, augmenting the usual
repository version information with pull requests and commit comments.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast, TYPE_CHECKING
import dateutil.tz
import github
from .repo import Git_Repository
from ..table import Table, Key_Table, Link_Table
from ..utils import convert_utc_datetime, format_date, get_local_datetime, \
    convert_local_datetime, parse_unicode
from ..version_control.repo import PathLike, Version
from ..version_control.review import Review_System
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
    from ..domain.source import GitHub
    import github.CommitComment
    import github.Issue
    import github.IssueComment
    import github.NamedUser
    import github.PullRequest
    import github.PullRequestComment
    import github.PullRequestReview
    import github.Repository
else:
    Project = object
    Source = object
    GitHub = object

CommentLike = Union[github.CommitComment.CommitComment,
                    github.PullRequestComment.PullRequestComment]
NoteLike = Union[CommentLike, github.IssueComment.IssueComment]
IssueLike = Union[github.Issue.Issue, github.PullRequest.PullRequest]

class GitHub_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by GitHub.
    """

    UPVOTE = 'APPROVED'
    DOWNVOTE = 'CHANGES_REQUESTED'

    UPDATE_TRACKER_NAME = 'github_update'

    AUXILIARY_TABLES = Git_Repository.AUXILIARY_TABLES | \
        Review_System.AUXILIARY_TABLES | {
            "github_repo", "merge_request_review",
            "github_issue", "github_issue_note"
        }

    def __init__(self, source: GitHub, repo_directory: PathLike,
                 project: Optional[Project] = None, **kwargs: Any) -> None:
        super().__init__(source, repo_directory, project=project, **kwargs)

        bots = source.get_option('github_bots')
        if bots is None:
            self._github_bots: Set[str] = set()
        else:
            self._github_bots = {bot.strip() for bot in bots.split(',')}

    @property
    def review_tables(self) -> Dict[str, Table]:
        review_tables = super().review_tables
        author = self.build_user_fields('author')
        assignee = self.build_user_fields('assignee')
        reviewer = self.build_user_fields('reviewer')
        review_tables.update({
            "github_repo": Key_Table('github_repo', 'github_id'),
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypt_fields=reviewer),
            "github_issue": Key_Table('github_issue', 'id',
                                      encrypt_fields=author + assignee),
            "github_issue_note": Link_Table('github_issue_note',
                                            ('issue_id', 'note_id'),
                                            encrypt_fields=author)
        })
        return review_tables

    @property
    def null_timestamp(self) -> str:
        # The datetime strftime() methods require year >= 1900.
        # This is used in get_data to retrieve API data since a given date.
        # All API responses have updated dates that stem from GitHub itself
        # and can thus not be earlier than GitHub's foundation.
        return "1900-01-01 01:01:01"

    @classmethod
    def is_up_to_date(cls, source: Source, latest_version: Version,
                      update_tracker: Optional[str] = None,
                      branch: Optional[str] = None) -> bool:
        if update_tracker is None or not isinstance(source, GitHub):
            return super(GitHub_Repository, cls).is_up_to_date(source,
                                                               latest_version,
                                                               branch=branch)

        try:
            repo = source.github_repo
        except RuntimeError:
            return False

        # Check if the API indicates that there are updates
        tracker_date = get_local_datetime(update_tracker)
        return tracker_date >= repo.updated_at.replace(tzinfo=dateutil.tz.tzutc())

    @property
    def source(self) -> GitHub:
        return cast(GitHub, self._source)

    @property
    def api(self) -> github.Github:
        """
        Retrieve an instance of the GitHub API connection for this source.
        """

        return self.source.github_api

    def get_data(self, from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None, force: bool = False,
                 **kwargs: Any) -> List[Dict[str, str]]:
        versions = super().get_data(from_revision, to_revision, force=force,
                                    **kwargs)

        self.fill_repo_table(self.source.github_repo)
        self._get_pull_requests()

        for commit_comment in self.source.github_repo.get_comments():
            self.add_commit_comment(commit_comment)

        self._get_issues()

        self.set_latest_date()

        return versions

    def _get_pull_requests(self) -> None:
        for pull_request in self.source.github_repo.get_pulls(state='all'):
            newer, reviews = self.add_pull_request(pull_request)
            if newer:
                for issue_comment in pull_request.get_issue_comments():
                    self.add_pull_comment(issue_comment, pull_request.number)
                for review_comment in pull_request.get_review_comments():
                    self.add_review_comment(review_comment, pull_request.number)
                for review in reviews:
                    self.add_review(review, pull_request.number)

    def _get_issues(self) -> None:
        since = convert_utc_datetime(self.tracker_date)
        for issue in self.source.github_repo.get_issues(state='all',
                                                        since=since):
            newer = self.add_issue(issue)
            if newer:
                for issue_comment in issue.get_comments(since=since):
                    self.add_issue_comment(issue_comment, issue.number)

    def fill_repo_table(self, repo: github.Repository.Repository) -> None:
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
            "create_time": format_date(convert_local_datetime(repo.created_at)),
            "private": private,
            "forked": forked,
            "star_count": str(repo.stargazers_count),
            "watch_count": str(repo.watchers_count)
        })

    @staticmethod
    def _get_username(part: Optional[github.NamedUser.NamedUser]) -> str:
        if part is None:
            return str(0)

        return parse_unicode(part.login)

    def _is_bot_user(self, user: github.NamedUser.NamedUser) -> bool:
        if user.type == "Bot":
            return True
        if user.login in self._github_bots:
            return True

        return False

    def _format_issue(self, issue: IssueLike) -> Dict[str, str]:
        author_username = self._get_username(issue.user)
        assignee_username = self._get_username(issue.assignee)
        return {
            'repo_name': str(self._repo_name),
            'id': str(issue.number),
            'title': parse_unicode(issue.title),
            'description': parse_unicode(issue.body),
            'status': issue.state,
            'author': author_username,
            'author_username': author_username,
            'assignee': assignee_username,
            'assignee_username': assignee_username,
            'created_at': format_date(convert_local_datetime(issue.created_at)),
            'updated_at': format_date(convert_local_datetime(issue.updated_at))
        }

    def add_pull_request(self, pull_request: github.PullRequest.PullRequest) \
            -> Tuple[bool, List[github.PullRequestReview.PullRequestReview]]:
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
        if request['status'] == 'closed' and pull_request.merged:
            request['status'] = 'merged'

        request.update({
            'source_branch': pull_request.head.ref,
            'target_branch': pull_request.base.ref,
            'upvotes': str(upvotes),
            'downvotes': str(downvotes)
        })
        self._tables["merge_request"].append(request)

        return True, list(reviews)

    def add_issue(self, issue: github.Issue.Issue) -> bool:
        """
        Add an issue described by its GitHub API response object to the repo
        issues table. Returns whether the issue is updated more recently than
        the update tracker date.
        """

        if not self._is_newer(issue.updated_at):
            return False

        pull_request_id = 0
        if issue.pull_request is not None:
            pulls_url = re.sub('{/[^}]+}', r'/(\d+)',
                               self.source.github_repo.pulls_url)
            pull_request_url: str = issue.pull_request.raw_data['url']
            match = re.match(pulls_url, pull_request_url)
            if match:
                pull_request_id = int(match.group(1))

        if issue.closed_at is not None:
            closed_date = format_date(convert_local_datetime(issue.closed_at))
        else:
            closed_date = str(0)

        issue_row = self._format_issue(issue)
        issue_row.update({
            'pull_request_id': str(pull_request_id),
            'labels': str(len(issue.labels)),
            'closed_at': closed_date,
            'closed_by': self._get_username(issue.closed_by)
        })
        self._tables["github_issue"].append(issue_row)

        return True

    def _format_note(self, comment: NoteLike) -> Dict[str, str]:
        author = self._get_username(comment.user)
        return {
            'repo_name': str(self._repo_name),
            'note_id': str(comment.id),
            'author': author,
            'author_username': author,
            'comment': parse_unicode(comment.body),
            'created_at': format_date(convert_local_datetime(comment.created_at)),
            'updated_at': format_date(convert_local_datetime(comment.updated_at))
        }

    def add_issue_comment(self, comment: github.IssueComment.IssueComment,
                          issue_id: int) -> bool:
        """
        Add an issue comment described by its GitHub API response object to the
        issue notes table. Returns whether the issue comment is updated more
        recently than the update tracker date.
        """

        if not self._is_newer(comment.updated_at):
            return False

        note = self._format_note(comment)
        note['issue_id'] = str(issue_id)
        self._tables["github_issue_note"].append(note)

        return True

    def add_pull_comment(self, comment: github.IssueComment.IssueComment,
                         request_id: int) -> bool:
        """
        Add a normal pull request comment described by its GitHub API response
        object to the repo merge request notes table. Returns whether the pull
        request comment is updated more recently than the update tracker date
        and is not a bot-generated comment.
        """

        if not self._is_newer(comment.updated_at):
            return False
        if self._is_bot_user(comment.user):
            return False

        note = self._format_note(comment)
        note.update({
            'thread_id': str(0),
            'parent_id': str(0),
            'merge_request_id': str(request_id)
        })

        self._tables["merge_request_note"].append(note)

        return True

    def _add_commit_comment(self, comment: CommentLike, **kwargs: Any) -> None:
        note = self._format_note(comment)
        note.update({
            'thread_id': str(0),
            'parent_id': str(0),
            'merge_request_id': str(kwargs.get('request_id', 0)),
            'created_date': note['created_at'],
            'updated_date': note['updated_at'],
            'file': comment.path,
            'line': str(kwargs.get('line', 0)),
            'end_line': str(kwargs.get('end_line', 0)),
            'line_type': str(kwargs.get('line_type', 0)),
            'commit_id': comment.commit_id
        })
        del note['created_at']
        del note['updated_at']
        self._tables["commit_comment"].append(note)

    def add_commit_comment(self, comment: github.CommitComment.CommitComment) -> bool:
        """
        Add a commit comment described by its GitHub API response object to the
        commit comments table. Returns whether the commit comment is updated
        more recently than the update tracker date and is not a bot-generated
        comment.
        """

        if not self._is_newer(comment.updated_at):
            return False
        if self._is_bot_user(comment.user):
            return False

        line = comment.line
        self._add_commit_comment(comment, line=line, end_line=line)
        return True

    def add_review_comment(self,
                           comment: github.PullRequestComment.PullRequestComment,
                           request_id: int = 0) -> bool:
        """
        Add a pull request review comment described by its GitHub API response
        object to the commit comments table. Returns whether the comment is
        updated more recently than the update tracker date and is not
        a bot-generated comment.
        """

        if not self._is_newer(comment.updated_at):
            return False
        if self._is_bot_user(comment.user):
            return False

        # We store the most recent line indexes to which the comment applies.
        position = comment.position
        if position is None:
            position = comment.original_position

        if comment.diff_hunk is not None and comment.diff_hunk.startswith('@@'):
            lines = comment.diff_hunk.split('\n')
            match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', lines[0])
            if match:
                line = int(match.group(3))
            else:
                line = 0

            end_line = line + position
            # Determine line type using the last line in the diff hunk.
            if lines[-1].startswith('-'):
                line_type = 'old'
            elif lines[-1].startswith('+'):
                line_type = 'new'
            else:
                line_type = 'context'
        else:
            line = position
            end_line = position

        self._add_commit_comment(comment, line=line, end_line=end_line,
                                 line_type=line_type, request_id=request_id)

        return True

    def add_review(self, review: github.PullRequestReview.PullRequestReview,
                   request_id: int) -> None:
        """
        Add a pull request review described by its GitHub API response object
        to the merge request reviews table.
        """

        if self._is_bot_user(review.user):
            return

        reviewer = self._get_username(review.user)
        if review.state == self.UPVOTE:
            vote = 1
        elif review.state == self.DOWNVOTE:
            vote = -1
        else:
            vote = 0

        self._tables["merge_request_review"].append({
            'repo_name': str(self._repo_name),
            'merge_request_id': str(request_id),
            'reviewer': reviewer,
            'reviewer_username': reviewer,
            'vote': str(vote)
        })
