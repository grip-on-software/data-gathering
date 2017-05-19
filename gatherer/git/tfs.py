"""
Module that handles access to a Team Foundation Server-based repository,
augmenting the usual repository version information such as pull requests.
"""

import logging
from git import Commit
import requests
from requests_ntlm import HttpNtlmAuth
from .repo import Git_Repository
from ..table import Table, Key_Table, Link_Table
from ..utils import Iterator_Limiter, parse_date, parse_unicode

class TFS_Project(object):
    """
    A project on a TFS server.
    """

    def __init__(self, host, collection, username, password):
        self._host = host
        self._collection = collection
        self._session = requests.Session()
        self._session.auth = HttpNtlmAuth(username, password, self._session)
        self._url = '{}/{}/_apis'.format(self._host, self._collection)

    def _get(self, path, api_version='1.0', **kw):
        params = kw.copy()
        params['api-version'] = api_version
        request = self._session.get(self._url + '/' + path, params=params)
        if request.status_code != requests.codes['ok']:
            try:
                data = request.json()
                if 'value' in data and 'Message' in data['value']:
                    message = 'HTTP error {}: {}'.format(request.status_code,
                                                         data['value']['Message'])
                elif 'message' in data:
                    message = '{}: {}'.format(data['typeKey'], data['message'])
                else:
                    raise ValueError

                raise RuntimeError(message)
            except ValueError:
                request.raise_for_status()

        return request.json()

    def _get_iterator(self, path, api_version='1.0', size=100, **kw):
        params = kw.copy()
        limiter = Iterator_Limiter(size=size)
        had_value = True
        values = []
        while limiter.check(had_value):
            had_value = False
            params['$skip'] = limiter.skip
            params['$top'] = limiter.size
            result = self._get(path, api_version=api_version, **params)
            if result['count'] > 0:
                values.extend(result['value'])
                had_value = True

            limiter.update()

        return values

    def repositories(self):
        """
        Retrieve the repositories that exist in the collection or project.
        """

        repositories = self._get('git/repositories')
        return repositories['value']

    def get_project_id(self, repository):
        """
        Determine the TFS project UUID that the given repository name
        belongs in.
        """

        repositories = self.repositories()
        for repository_data in repositories:
            if repository_data['name'] == repository:
                return repository_data['project']['id']

        raise ValueError("Repository '{}' cannot be found".format(repository))

    def get_repository_id(self, repository):
        """
        Determine the TFS repository UUID for the given repository name.
        """

        repositories = self.repositories()
        for repository_data in repositories:
            if repository_data['name'] == repository:
                return repository_data['id']

        raise ValueError("Repository '{}' cannot be found".format(repository))

    def pushes(self, repository, refs=True):
        """
        Retrieve information about Git pushes to a certain repository in the
        project.
        """

        path = 'git/repositories/{}/pushes'.format(repository)
        return self._get_iterator(path, includeRefUpdates=str(refs))

    def pull_requests(self, repository=None, status='All'):
        """
        Retrieve information about pull requests from a repository or from
        the entire collection or project.
        """

        if repository is not None:
            path = 'git/repositories/{}/pullRequests'.format(repository)
        else:
            path = 'git/pullRequests'

        try:
            return self._get_iterator(path, status=status)
        except RuntimeError:
            # The TFS API returns an error if there are no pull requests.
            return []

    def pull_request_comments(self, project_id, request_id):
        """
        Retrieve infromation about code review comments in a pull request.
        """

        artifact = 'vstfs:///CodeReview/CodeReviewId/{}%2F{}'.format(project_id,
                                                                     request_id)
        comments = self._get('discussion/threads', api_version='3.0-preview.1',
                             artifactUri=artifact)
        return comments['value']

class TFS_Repository(Git_Repository):
    """
    Git repository hosted by a TFS server.
    """

    PROPERTY = 'Microsoft.TeamFoundation.Discussion'

    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(TFS_Repository, self).__init__(source, repo_directory,
                                             project=project, **kwargs)

        self._project_id = None

        author_fields = ('author', 'author_username')
        review_fields = ('reviewer', 'reviewer_username')
        self._tables.update({
            "merge_request": Key_Table('merge_request', 'id',
                                       encrypted_fields=author_fields),
            "merge_request_note": Link_Table('merge_request_note',
                                             ('merge_request_id', 'note_id'),
                                             encrypted_fields=author_fields),
            "commit_comment": Table('commit_comment',
                                    encrypted_fields=author_fields),
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypted_fields=review_fields),
            "vcs_event": Table('vcs_event', encrypted_fields=('user', 'email'))
        })

    @property
    def api(self):
        """
        Retrieve an instance of the TFS API connection for the TFS collection
        on this host.
        """

        return self._source.tfs_api

    @property
    def project_id(self):
        """
        Retrieve the UUID of the project that contains this repository.
        """

        if self._project_id is None:
            self._project_id = self.api.get_project_id(self.repo_name)

        return self._project_id

    def get_data(self, **kwargs):
        versions = super(TFS_Repository, self).get_data(**kwargs)

        repository_id = self.api.get_repository_id(self.repo_name)
        for event in self.api.pushes(repository_id, refs=True):
            self.add_event(event)

        for pull_request in self.api.pull_requests(repository_id):
            self.add_pull_request(pull_request)

        return versions

    def add_pull_request(self, pull_request):
        """
        Add a pull request described by its TFS API response object to the
        pull requests table.
        """

        if 'reviewers' in pull_request:
            reviewers = pull_request['reviewers']
        else:
            reviewers = []

        upvotes = len([1 for reviewer in reviewers if reviewer['vote'] > 0])
        downvotes = len([1 for reviewer in reviewers if reviewer['vote'] < 0])

        if 'closedDate' in pull_request:
            updated_date = pull_request['closedDate']
        else:
            updated_date = pull_request['creationDate']

        if 'description' in pull_request:
            description = pull_request['description']
        else:
            description = ''

        request_id = str(pull_request['pullRequestId'])
        self._tables["merge_request"].append({
            'repo_name': str(self._repo_name),
            'id': request_id,
            'title': parse_unicode(pull_request['title']),
            'description': parse_unicode(description),
            'status': str(pull_request['status']),
            'source_branch': pull_request['sourceRefName'],
            'target_branch': pull_request['targetRefName'],
            'author': parse_unicode(pull_request['createdBy']['displayName']),
            'author_username': pull_request['createdBy']['uniqueName'],
            'assignee': str(0),
            'assignee_username': str(0),
            'upvotes': str(upvotes),
            'downvotes': str(downvotes),
            'created_at': parse_date(pull_request['creationDate']),
            'updated_at': parse_date(updated_date)
        })

        for reviewer in reviewers:
            self.add_review(request_id, reviewer)

        comments = self.api.pull_request_comments(self.project_id, request_id)
        for comment in comments:
            self.add_comment(request_id, comment)

    @staticmethod
    def _is_container_account(author):
        return 'isContainer' in author and author['isContainer']

    def add_review(self, request_id, reviewer):
        """
        Add a pull request review described by its TFS API response object to
        the pull request reviews table.
        """

        # Ignore project team container accounts (aggregate votes)
        if not self._is_container_account(reviewer):
            self._tables["merge_request_review"].append({
                'repo_name': str(self._repo_name),
                'merge_request_id': request_id,
                'reviewer': parse_unicode(reviewer['uniqueName']),
                'reviewer_name': parse_unicode(reviewer['displayName']),
                'vote': str(reviewer['vote'])
            })

    def add_comment(self, request_id, thread):
        """
        Add a pull request code review comment described by its TFS API
        response object to the pull request notes table.
        """

        properties = thread['properties']
        for comment in thread['comments']:
            if self._is_container_account(comment['author']):
                continue
            if comment['isDeleted']:
                continue

            parent_id = comment['parentId'] if 'parentId' in comment else 0
            if 'uniqueName' not in comment['author'] or comment['content'] is None:
                logging.info(request_id)
                logging.info(thread)
                logging.info(comment)

            note = {
                'repo_name': str(self._repo_name),
                'merge_request_id': request_id,
                'thread_id': str(thread['id']),
                'note_id': str(comment['id']),
                'parent_id': str(parent_id),
                'author': parse_unicode(comment['author']['displayName']),
                'author_username': comment['author']['uniqueName'],
                'comment': parse_unicode(comment['content']),
                'created_at': parse_date(comment['publishedDate']),
                'updated_at': parse_date(comment['lastUpdatedDate']),
            }

            # Determine whether to add as commit comment or request note
            if self.PROPERTY + '.ItemPath' in properties:
                self.add_commit_comment(note, properties)
            else:
                self._tables["merge_request_note"].append(note)

    def add_commit_comment(self, note, properties):
        """
        Add a pull request code review file comment described by its incomplete
        note dictionary and the thread properties from the TFS API response
        to the commit comments table.
        """

        if self.PROPERTY + '.Position.PositionContext' in properties:
            context = properties[self.PROPERTY + '.Position.PositionContext']
            if context['$value'] == 'LeftBuffer':
                line_type = 'old'
            else:
                line_type = 'new'
        else:
            line_type = str(0)

        if self.PROPERTY + '.Position.StartLine' in properties:
            line = properties[self.PROPERTY + '.Position.StartLine']['$value']
        else:
            line = 0

        if self.PROPERTY + '.Position.EndLine' in properties:
            end_line = properties[self.PROPERTY + '.Position.EndLine']['$value']
        else:
            end_line = 0

        note.update({
            'file': properties[self.PROPERTY + '.ItemPath']['$value'],
            'line': str(line),
            'end_line': str(end_line),
            'line_type': line_type,
            'commit_id': properties['CodeReviewTargetCommit']['$value']
        })
        self._tables["commit_comment"].append(note)

    def add_event(self, event):
        """
        Add a push event from the TFS API.
        """

        # Ignore incomplete/group/automated accounts
        if event['pushedBy']['uniqueName'].startswith('vstfs:///'):
            return

        for ref_update in event['refUpdates']:
            commit_id = ref_update['newObjectId']
            # pylint: disable=no-member
            if ref_update['oldObjectId'] == Commit.NULL_HEX_SHA:
                action = 'pushed new'
            elif ref_update['newObjectId'] == Commit.NULL_HEX_SHA:
                action = 'deleted'
                commit_id = ref_update['oldObjectId']
            else:
                action = 'pushed to'

            self._tables["vcs_event"].append({
                'repo_name': str(self._repo_name),
                'version_id': str(commit_id),
                'action': action,
                'kind': 'push',
                'ref': str(ref_update['name']),
                'user': parse_unicode(event['pushedBy']['uniqueName']),
                'user_name': parse_unicode(event['pushedBy']['displayName']),
                'date': parse_date(event['date'])
            })
