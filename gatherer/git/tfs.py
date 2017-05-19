"""
Module that handles access to a GitLab-based repository, augmenting the usual
repository version information such as pull requests.
"""

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
        Retrieve informatino about pull requests from a repository or from
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

class TFS_Repository(Git_Repository):
    """
    Git repository hosted by a TFS server.
    """

    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(TFS_Repository, self).__init__(source, repo_directory,
                                             project=project, **kwargs)

        author_fields = ('author', 'author_username')
        review_fields = ('reviewer', 'reviewer_username')
        self._tables.update({
            "merge_request": Key_Table('merge_request', 'id',
                                       encrypted_fields=author_fields),
            "merge_request_note": Link_Table('merge_request_note',
                                             ('merge_request_id', 'note_id'),
                                             encrypted_fields=author_fields),
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypted_fields=review_fields),
            "vcs_event": Table('vcs_event', encrypted_fields=('user', 'email'))
        })

    @property
    def api(self):
        """
        Retrieve an instance of the TFS API connecrtion for the TFS collection
        on this host.
        """

        return self._source.tfs_api

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

        self._tables["merge_request"].append({
            'repo_name': str(self._repo_name),
            'id': str(pull_request['pullRequestId']),
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
            if 'isContainer' not in reviewer or not reviewer['isContainer']:
                self._tables["merge_request_review"].append({
                    'repo_name': str(self._repo_name),
                    'merge_request_id': str(pull_request['pullRequestId']),
                    'reviewer': parse_unicode(reviewer['uniqueName']),
                    'reviewer_name': parse_unicode(reviewer['displayName']),
                    'vote': str(reviewer['vote'])
                })

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
