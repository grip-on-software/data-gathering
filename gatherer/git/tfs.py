"""
Module that handles access to a Team Foundation Server-based repository,
augmenting the usual repository version information such as pull requests.
"""

import datetime
import re
import dateutil.tz
from git import Commit
import requests
from requests_ntlm import HttpNtlmAuth
from .repo import Git_Repository
from ..table import Table, Key_Table, Link_Table
from ..utils import get_local_datetime, convert_local_datetime, format_date, \
    parse_date, parse_unicode, Iterator_Limiter

class TFS_Project(object):
    """
    A project on a TFS server.
    """

    def __init__(self, host, collections, username, password):
        self._host = host
        self._collection = collections[0]
        if len(collections) > 1:
            self._project = collections[1]
        else:
            self._project = None

        self._session = requests.Session()
        self._session.auth = HttpNtlmAuth(username, password, self._session)
        self._url = '{}/{}'.format(self._host, self._collection)

    @classmethod
    def _validate_request(cls, request):
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

    def _get(self, area, path, api_version='1.0', project_collection=False, **kw):
        params = kw.copy()
        params['api-version'] = api_version

        if self._project is None:
            parts = (self._url, '_apis', area, path)
        elif project_collection:
            parts = (self._url, self._project, '_apis', area, path)
        else:
            parts = (self._url, '_apis', area, self._project, path)

        url = '/'.join(parts)
        request = self._session.get(url, params=params)
        self._validate_request(request)

        return request.json()

    def _get_iterator(self, area, path, api_version='1.0', size=100, **kw):
        params = kw.copy()
        limiter = Iterator_Limiter(size=size)
        had_value = True
        values = []
        while limiter.check(had_value):
            had_value = False
            params['$skip'] = limiter.skip
            params['$top'] = limiter.size
            result = self._get(area, path, api_version=api_version, **params)
            if result['count'] > 0:
                values.extend(result['value'])
                had_value = True

            limiter.update()

        return values

    def repositories(self):
        """
        Retrieve the repositories that exist in the collection or project.
        """

        repositories = self._get('git', 'repositories')
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

    def pushes(self, repository, from_date=None, refs=True):
        """
        Retrieve information about Git pushes to a certain repository in the
        project.
        """

        path = 'repositories/{}/pushes'.format(repository)
        pushes = self._get_iterator('git', path, fromDate=from_date,
                                    includeRefUpdates=str(refs))

        if refs and len(pushes) > 0 and 'refUpdates' not in pushes[0]:
            # TFS 2013 support
            for push in pushes:
                push_details = self._get('git',
                                         '{}/{}'.format(path, push['pushId']))
                push['pushedBy']['uniqueName'] = push['pushedBy']['displayName']
                push['refUpdates'] = []
                for commit in push_details['commits']:
                    push['refUpdates'].append({
                        'newObjectId': commit['commitId'],
                        'oldObjectId': commit['commitId']
                    })

        return pushes

    def pull_requests(self, repository=None, status='All'):
        """
        Retrieve information about pull requests from a repository or from
        the entire collection or project.
        """

        if repository is not None:
            path = 'repositories/{}/pullRequests'.format(repository)
        else:
            path = 'pullRequests'

        if status == 'All':
            url = '{}/_apis/git/pullRequests'.format(self._url)
            request = self._session.options(url)
            self._validate_request(request)
            options = request.json()
            if options['value'][0]['releasedVersion'] == '0.0':
                # TFS 2013 compatibility
                return self._pull_requests(path, 'Active') + \
                        self._pull_requests(path, 'Completed') + \
                        self._pull_requests(path, 'Abandoned')

        return self._pull_requests(path, status, project_collection=True)

    def _pull_requests(self, path, status, **kw):
        try:
            return self._get_iterator('git', path, status=status, **kw)
        except RuntimeError:
            # The TFS API returns an error if there are no pull requests.
            return []

    def pull_request(self, repository, request_id):
        """
        Retrieve information about a single pull request.
        """

        path = 'repositories/{}/pullRequests/{}'.format(repository, request_id)
        return self._get('git', path)

    def pull_request_comments(self, project_id, request_id):
        """
        Retrieve infromation about code review comments in a pull request.
        """

        artifact = 'vstfs:///CodeReview/CodeReviewId/{}%2F{}'.format(project_id,
                                                                     request_id)
        comments = self._get('discussion', 'threads',
                             api_version='3.0-preview.1', artifactUri=artifact)
        return comments['value']

class TFS_Repository(Git_Repository):
    """
    Git repository hosted by a TFS server.
    """

    # Key prefix to use to retrieve certain commit comment properties.
    PROPERTY = 'Microsoft.TeamFoundation.Discussion'

    # Timestamp to use as a default for the update tracker. This timestamp
    # must be within the valid range of TFS DateTime fields, which must not
    # be earlier than the year 1753 due to the Gregorian calendar.
    TFS_NULL_TIMESTAMP = "1900-01-01 01:01:01"

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

        self._update_trackers["tfs_update"] = self.TFS_NULL_TIMESTAMP
        self._previous_date = None
        self._latest_date = None

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
            self._project_id = self.api.get_project_id(self._source.tfs_repo)

        return self._project_id

    def set_update_tracker(self, file_name, value):
        super(TFS_Repository, self).set_update_tracker(file_name, value)
        self._previous_date = None
        self._latest_date = None

    def _is_newer(self, date):
        date = self._parse_date(date)
        if self._previous_date is None:
            self._previous_date = get_local_datetime(self._update_trackers['tfs_update'])
            self._latest_date = self._previous_date

        if date > self._previous_date:
            self._latest_date = max(date, self._latest_date)
            return True

        return False

    @staticmethod
    def _parse_date(date):
        if date.endswith('Z'):
            date = date[:-1]
        match = re.match(r'(.*)\.([0-9]{1,6})[0-9]*Z?$', date)
        if match:
            date = match.group(1)
            microsecond = int(match.group(2))
        else:
            microsecond = 0

        parsed_date = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
        return parsed_date.replace(microsecond=microsecond,
                                   tzinfo=dateutil.tz.tzutc())

    def get_data(self, **kwargs):
        versions = super(TFS_Repository, self).get_data(**kwargs)

        repository_id = self.api.get_repository_id(self._source.tfs_repo)
        events = self.api.pushes(repository_id, refs=True,
                                 from_date=self._update_trackers['tfs_update'])
        for event in events:
            self.add_event(event)

        for pull_request in self.api.pull_requests(repository_id):
            self.add_pull_request(repository_id, pull_request)

        if self._latest_date is not None:
            latest_date = format_date(convert_local_datetime(self._latest_date))
            self._update_trackers['tfs_update'] = latest_date

        return versions

    def add_pull_request(self, repository_id, pull_request):
        """
        Add a pull request described by its TFS API response object to the
        pull requests table.
        """

        request_id = str(pull_request['pullRequestId'])
        if 'reviewers' in pull_request:
            reviewers = pull_request['reviewers']
        elif '_links' not in pull_request:
            # Retrieve the reviewers from the pull request itself for TFS 2013
            request = self.api.pull_request(repository_id, request_id)
            reviewers = request['reviewers'] if 'reviewers' in request else []
        else:
            reviewers = []

        upvotes = len([1 for reviewer in reviewers if reviewer['vote'] > 0])
        downvotes = len([1 for reviewer in reviewers if reviewer['vote'] < 0])

        if 'closedDate' in pull_request:
            updated_date = pull_request['closedDate']

            if not self._is_newer(updated_date):
                return
        else:
            updated_date = pull_request['creationDate']

        if 'description' in pull_request:
            description = pull_request['description']
        else:
            description = ''

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
    def _is_container_account(author, display_name):
        if isinstance(author, dict) and 'isContainer' in author:
            return author['isContainer']

        # Fall back to checking for group team account names
        if re.match(r'^\[[^\]]+]\\', display_name):
            return True

        return False

    def add_review(self, request_id, reviewer):
        """
        Add a pull request review described by its TFS API response object to
        the pull request reviews table.
        """

        # Ignore project team container accounts (aggregate votes)
        if not self._is_container_account(reviewer, reviewer['uniqueName']):
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
            if 'authorDisplayName' in comment:
                display_name = comment['authorDisplayName']
            else:
                display_name = comment['author']['displayName']

            if self._is_container_account(comment['author'], display_name):
                continue
            if comment['isDeleted']:
                continue
            if not self._is_newer(comment['lastUpdatedDate']):
                continue

            if 'authorDisplayName' in comment:
                unique_name = display_name
            else:
                unique_name = comment['author']['uniqueName']

            parent_id = comment['parentId'] if 'parentId' in comment else 0

            note = {
                'repo_name': str(self._repo_name),
                'merge_request_id': request_id,
                'thread_id': str(thread['id']),
                'note_id': str(comment['id']),
                'parent_id': str(parent_id),
                'author': parse_unicode(display_name),
                'author_username': parse_unicode(unique_name),
                'comment': parse_unicode(comment['content']),
                'created_at': parse_date(comment['publishedDate']),
                'updated_at': parse_date(comment['lastUpdatedDate'])
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
            'created_date': note['created_at'],
            'updated_date': note['updated_at'],
            'file': properties[self.PROPERTY + '.ItemPath']['$value'],
            'line': str(line),
            'end_line': str(end_line),
            'line_type': line_type,
            'commit_id': properties['CodeReviewTargetCommit']['$value']
        })
        del note['created_at']
        del note['updated_at']
        self._tables["commit_comment"].append(note)

    def add_event(self, event):
        """
        Add a push event from the TFS API.
        """

        # Ignore incomplete/group/automated accounts
        if event['pushedBy']['uniqueName'].startswith('vstfs:///'):
            return

        if not self._is_newer(event['date']):
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

            if 'name' in ref_update:
                ref_name = str(ref_update['name'])
            else:
                ref_name = str(0)

            self._tables["vcs_event"].append({
                'repo_name': str(self._repo_name),
                'version_id': str(commit_id),
                'action': action,
                'kind': 'push',
                'ref': ref_name,
                'user': parse_unicode(event['pushedBy']['uniqueName']),
                'user_name': parse_unicode(event['pushedBy']['displayName']),
                'date': parse_date(event['date'])
            })
