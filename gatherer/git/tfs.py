"""
Module that handles access to a Team Foundation Server-based repository,
augmenting the usual repository version information such as pull requests.

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

import itertools
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, \
    Union, cast, TYPE_CHECKING
from git import Commit
from requests.auth import HTTPBasicAuth, AuthBase
from requests.exceptions import HTTPError
from requests.models import Response
from requests_ntlm import HttpNtlmAuth
from .repo import Git_Repository
from ..request import Session
from ..table import Table, Key_Table, Link_Table
from ..vsts.parser import Field_Parser, String_Parser, Int_Parser, \
    Date_Parser, Unicode_Parser, Decimal_Parser, Tags_Parser, Developer_Parser
from ..utils import get_local_datetime, parse_utc_date, parse_unicode, \
    Iterator_Limiter
from ..version_control.review import Review_System
from ..version_control.repo import PathLike, Version
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
    from ..domain.source.tfs import TFS, TFVC, TFS_Collection
else:
    Project = object
    Source = object
    TFS = object
    TFVC = object
    TFS_Collection = tuple

Project_Collection = Optional[Union[str, bool]]
Work_Item_Fields = Dict[str, Dict[str, Union[str, List[str]]]]
Result = Dict[str, Any]

class TFS_Project:
    """
    A project using Git on a TFS or VSTS server.
    """

    def __init__(self, host: str, collections: TFS_Collection,
                 username: str, password: str) -> None:
        self._host = host
        self._collection = collections[0]

        self._project: Optional[str] = None
        if len(collections) > 1:
            self._project = collections[1]

        self._session = Session(auth=self._make_auth(username, password))
        self._url = f'{self._host}/{self._collection}'

    @classmethod
    def _make_auth(cls, username: str, password: str) -> AuthBase:
        return HttpNtlmAuth(username, password)

    def _perform_request(self, url: str, params: Dict[str, str]) \
            -> Tuple[Optional[Result], Optional[Exception]]:
        try:
            request = self._session.get(url, params=params)
            self._validate_request(request)

            return request.json(), None
        except (RuntimeError, ValueError, HTTPError) as error:
            return None, error

    @classmethod
    def _validate_request(cls, request: Response) -> None:
        if not Session.is_code(request, 'ok'):
            try:
                data = request.json()
                if 'value' in data and 'Message' in data['value']:
                    text = data['value']['Message']
                    message = f'HTTP error {request.status_code}: {text}'
                elif 'message' in data:
                    message = f"{data['typeKey']}: {data['message']}"
                else:
                    raise ValueError

                raise RuntimeError(message)
            except ValueError:
                request.raise_for_status()

    def _get_url_candidates(self, area: str, path: str,
                            project_collection: Project_Collection = False) \
                            -> List[Tuple[str, ...]]:
        if self._project is None or project_collection is None:
            if isinstance(project_collection, str):
                return [(self._url, project_collection, '_apis', area, path)]

            return [(self._url, '_apis', area, path)]
        if project_collection is True:
            return [(self._url, self._project, '_apis', area, path)]
        if isinstance(project_collection, str):
            return [(self._url, project_collection, '_apis', area, path)]

        return [
            (self._url, self._project, '_apis', area, path), # TFS 2017+
            (self._url, '_apis', area, self._project, path) # TFS 2015
        ]

    def _get(self, area: str, path: str, api_version: str = '1.0',
             project_collection: Project_Collection = False, **kw: str) -> Result:
        params = kw.copy()
        params['api-version'] = api_version

        candidates = self._get_url_candidates(area, path, project_collection)

        # Attempt all candidate URLs before giving up.
        error = None
        for parts in candidates:
            url = '/'.join(parts)
            result, error = self._perform_request(url, params)
            if result is not None:
                return result

        # pylint: disable=raising-bad-type
        raise RuntimeError(f'Cannot find a suitable API URL: {error}')

    def _get_iterator(self, area: str, path: str, api_version: str = '1.0',
                      options: Optional[Union[str, Dict[str, Any]]] = None,
                      project_collection: Project_Collection = False,
                      **kw: str) -> Iterator[Result]:
        if options is None:
            options = {}
        elif isinstance(options, str):
            options = {options: True}

        params = kw.copy()
        limiter = Iterator_Limiter(size=options.get('size', 100))
        had_value = True
        while limiter.check(had_value):
            had_value = False
            params['$skip'] = str(limiter.skip)
            params['$top'] = str(limiter.size)

            try:
                result = self._get(area, path,
                                   api_version=api_version,
                                   project_collection=project_collection,
                                   **params)
            except RuntimeError:
                if options.get('empty_on_error', False):
                    # The TFS API sometimes returns an error for empty results.
                    return

                raise

            if result['count'] > 0:
                had_value = True
                for value in result['value']:
                    yield value

            limiter.update()

    def _get_continuation(self, area: str, path: str, api_version: str = '3.0',
                          **kw: str) -> Iterator[Result]:
        params = kw.copy()
        params['api-version'] = api_version

        is_last_batch = False
        url = '/'.join(self._get_url_candidates(area, path)[0])
        while not is_last_batch:
            result, error = self._perform_request(url, params)
            if result is None:
                raise RuntimeError(f'Could not obtain continuation result: {error}')

            is_last_batch = result['isLastBatch'] and result['values']
            url = result['nextLink']

            for value in result['values']:
                yield value

    def repositories(self) -> List[Result]:
        """
        Retrieve the repositories that exist in the collection or project.
        """

        repositories = self._get('git', 'repositories')
        return repositories['value']

    def get_project_id(self, repository: str) -> str:
        """
        Determine the TFS project UUID that the given repository name
        belongs in.
        """

        repositories = self.repositories()
        for repository_data in repositories:
            if repository_data['name'].lower() == repository.lower():
                return repository_data['project']['id']

        raise ValueError(f"Repository '{repository}' cannot be found")

    def get_repository_id(self, repository: str) -> str:
        """
        Determine the TFS repository UUID for the given repository name.
        """

        repositories = self.repositories()
        for repository_data in repositories:
            if repository_data['name'].lower() == repository.lower():
                return repository_data['id']

        raise ValueError(f"Repository '{repository}' cannot be found")

    def _update_push_refs(self, path: str, push: Result) -> Result:
        push_id = str(push['pushId'])
        push_details = self._get('git', f'{path}/{push_id}')
        push['pushedBy']['uniqueName'] = push['pushedBy']['displayName']
        push['refUpdates'] = []
        for commit in push_details['commits']:
            push['refUpdates'].append({
                'newObjectId': commit['commitId'],
                'oldObjectId': commit['commitId']
            })

        return push

    def pushes(self, repository: str, from_date: Optional[str] = None,
               refs: bool = True) -> Iterator[Result]:
        """
        Retrieve information about Git pushes to a certain repository in the
        project. The push data is provided as an iterator.
        """

        path = f'repositories/{repository}/pushes'
        params: Dict[str, str] = {
            'includeRefUpdates': str(refs)
        }
        if from_date is not None:
            params['fromDate'] = from_date

        pushes = self._get_iterator('git', path, **params)

        try:
            first_push = next(pushes)
        except StopIteration:
            return iter([])

        chain = itertools.chain([first_push], pushes)
        if refs and 'refUpdates' not in first_push:
            # TFS 2013 support
            return iter(self._update_push_refs(path, push) for push in chain)

        return chain

    def pull_requests(self, repository: Optional[str] = None,
                      status: str = 'All') -> Iterator[Result]:
        """
        Retrieve information about pull requests from a repository or from
        the entire collection or project. The pull request data is returned as
        an iterator.
        """

        if repository is not None:
            path = f'repositories/{repository}/pullRequests'
        else:
            path = 'pullRequests'

        if status == 'All':
            url = f'{self._url}/_apis/git/pullRequests'
            request = self._session.options(url)
            self._validate_request(request)
            options = request.json()
            if options['value'][0]['releasedVersion'] == '0.0':
                # TFS 2013 compatibility
                return itertools.chain(self._pull_requests(path, 'Active'),
                                       self._pull_requests(path, 'Completed'),
                                       self._pull_requests(path, 'Abandoned'))

        return self._pull_requests(path, status, project_collection=True)

    def _pull_requests(self, path: str, status: str,
                       project_collection: Project_Collection = False,
                       **kw: str) -> Iterator[Result]:
        return self._get_iterator('git', path, status=status,
                                  options={'empty_on_error': True},
                                  project_collection=project_collection, **kw)

    def pull_request(self, repository: str, request_id: str) -> Result:
        """
        Retrieve information about a single pull request.
        """

        path = f'repositories/{repository}/pullRequests/{request_id}'
        return self._get('git', path)

    def pull_request_comments(self, project_id: str, request_id: str) -> List[Result]:
        """
        Retrieve infromation about code review comments in a pull request.
        """

        artifact = f'vstfs:///CodeReview/CodeReviewId/{project_id}%2F{request_id}'
        comments = self._get('discussion', 'threads',
                             api_version='3.0-preview.1', artifactUri=artifact)
        return comments['value']

    def teams(self, project: str) -> Iterator[Result]:
        """
        Retrieve information about teams in a project.

        The team data is returned as an iterator.
        """

        return self._get_iterator('projects', f'{project}/teams',
                                  project_collection=None)

    def team_members(self, project: str, team: str) -> Iterator[Result]:
        """
        Retrieve information about teams in a project's team.

        The team member data is returned as an iterator.
        """

        return self._get_iterator('projects',
                                  f'{project}/teams/{team}/members',
                                  project_collection=None)

    def sprints(self, project: str, team: Optional[str] = None) -> List[Result]:
        """
        Retrieve information about sprints for a project or a project's team.

        The sprint data is returned as an iterator.
        """

        if team is None:
            project_collection = project
        else:
            project_collection = f'{project}/{team}'

        return self._get('work', 'teamsettings/iterations',
                         project_collection=project_collection,
                         api_version='3.0')['value']

    def work_item_revisions(self, ids: Optional[Sequence[int]] = None,
                            fields: Optional[Sequence[str]] = None,
                            from_date: Optional[str] = None) \
            -> Iterator[Result]:
        """
        Retrieve information about work items.

        The work item data is returned as an iterator.
        """

        params: Dict[str, str] = {}
        if fields is not None:
            params['fields'] = ','.join(fields)
        if from_date is not None:
            params['startDateTime'] = from_date

        if ids is not None:
            params.update({
                'ids': ','.join(str(work_id) for work_id in ids),
                'errorPolicy': 'Omit',
                'expand': 'All'
            })
            if from_date is not None:
                params['asOf'] = params.pop('startDateTime')

            return self._get_iterator('wit', 'workitems', **params)

        return self._get_continuation('wit', 'reporting/workitemrevisions',
                                      **params)

class TFVC_Project(TFS_Project):
    """
    A project using TFVC on a TFS or VSTS server.
    """

    @classmethod
    def _make_auth(cls, username: str, password: str) -> AuthBase:
        return HTTPBasicAuth(username, password)

    def projects(self) -> List[Result]:
        """
        Retrieve the projects that exist on the server.
        """

        projects = self._get('projects', '', project_collection=None)
        return projects['value']

    def branches(self) -> List[Result]:
        """
        Retrieve the branches that exist for the project.
        """

        branches = self._get('tfvc', 'branches')
        return branches['value']

    def get_project_id(self, repository: str) -> str:
        if self._project is None:
            raise ValueError('No project collection provided in URL')

        try:
            project = self._get('projects', self._project,
                                project_collection=None)
            return project['id']
        except (RuntimeError, KeyError) as error:
            raise ValueError(f"Repository '{repository}' cannot be found") from error

class TFS_Repository(Git_Repository, Review_System):
    """
    Git repository hosted by a TFS server.
    """

    # Key prefix to use to retrieve certain commit comment properties.
    PROPERTY = 'Microsoft.TeamFoundation.Discussion'

    UPDATE_TRACKER_NAME = 'tfs_update'

    AUXILIARY_TABLES = Git_Repository.AUXILIARY_TABLES | \
        Review_System.AUXILIARY_TABLES | {"merge_request_review", "vcs_event"}

    def __init__(self, source: Source, repo_directory: PathLike,
                 project: Optional[Project] = None, **kwargs: Any) -> None:
        super().__init__(source, repo_directory, project=project, **kwargs)

        self._project_id: Optional[str] = None

    @property
    def review_tables(self) -> Dict[str, Table]:
        review_tables = super().review_tables
        review_fields = self.build_user_fields('reviewer')
        review_tables.update({
            "merge_request_review": Link_Table('merge_request_review',
                                               ('merge_request_id', 'reviewer'),
                                               encrypt_fields=review_fields),
            "vcs_event": Table('vcs_event',
                               encrypt_fields=('user', 'username', 'email')),
            "tfs_team": Link_Table('tfs_team', ('repo_name', 'team_name')),
            "tfs_team_member": Link_Table('tfs_team_member',
                                          ('repo_name', 'team_name', 'user'),
                                          encrypt_fields=('user', 'username')),
            "tfs_sprint": Link_Table('tfs_sprint',
                                     ('repo_name', 'team_name', 'sprint_name')),
            "tfs_work_item": Link_Table('tfs_work_item',
                                        ('issue_id', 'changelog_id'),
                                        encrypt_fields=('reporter', 'assignee',
                                                        'updated_by')),
            "tfs_developer": Key_Table('tfs_developer', 'display_name',
                                       encrypt_fields=('display_name', 'email'))
        })
        return review_tables

    @property
    def null_timestamp(self) -> str:
        # Timestamp to use as a default for the update tracker. This timestamp
        # must be within the valid range of TFS DateTime fields, which must not
        # be earlier than the year 1753 due to the Gregorian calendar.
        return "1900-01-01 01:01:01"

    @property
    def source(self) -> TFS:
        return cast(TFS, self._source)

    @property
    def api(self) -> TFS_Project:
        """
        Retrieve an instance of the TFS API connection for the TFS collection
        on this host.
        """

        return self.source.tfs_api

    @property
    def project_id(self) -> str:
        """
        Retrieve the UUID of the project that contains this repository.
        """

        if self.source.tfs_repo is None:
            raise ValueError('No project collection repository provided in URL')

        if self._project_id is None:
            self._project_id = self.api.get_project_id(self.source.tfs_repo)

        return self._project_id

    @classmethod
    def _get_ssh_command(cls, source: Source) -> str:
        ssh_command = super(TFS_Repository, cls)._get_ssh_command(source)
        return f'{ssh_command} -c +aes256-cbc,aes192-cbc,aes128-cbc'

    def get_data(self, from_revision: Optional[Version] = None,
                 to_revision: Optional[Version] = None, force: bool = False,
                 **kwargs: Any) -> List[Result]:
        versions = super().get_data(from_revision, to_revision, force=force,
                                    **kwargs)

        if self.source.tfs_repo is not None:
            self._get_repo_data()

        for team in self.api.teams(self.project_id):
            self.add_team(team)

        self.add_work_item_revisions()

        self.set_latest_date()

        return versions

    def _get_repo_data(self) -> None:
        if self.source.tfs_repo is None:
            logging.warning('No project collection repository provided in URL')
            return

        try:
            repository_id = self.api.get_repository_id(self.source.tfs_repo)
        except (RuntimeError, ValueError):
            logging.exception('Could not retrieve repository ID for %s',
                              self.source.tfs_repo)
            return

        events = self.api.pushes(repository_id, refs=True,
                                 from_date=self._update_trackers['tfs_update'])
        for event in events:
            self.add_event(event)

        for pull_request in self.api.pull_requests(repository_id):
            self.add_pull_request(repository_id, pull_request)

    def add_pull_request(self, repository_id: str,
                         pull_request: Result) -> None:
        """
        Add a pull request described by its TFS API response object to the
        merge requests table.
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

        created_date = parse_utc_date(pull_request['creationDate'])
        if 'closedDate' in pull_request:
            updated_date = parse_utc_date(pull_request['closedDate'])

            if not self._is_newer(get_local_datetime(updated_date)):
                return
        else:
            updated_date = created_date

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
            'created_at': created_date,
            'updated_at': updated_date
        })

        for reviewer in reviewers:
            self.add_review(request_id, reviewer)

        comments = self.api.pull_request_comments(self.project_id, request_id)
        for thread in comments:
            self.add_thread_comments(request_id, thread)

    @staticmethod
    def _is_container_account(author: Union[Result, str],
                              display_name: str) -> bool:
        if isinstance(author, dict) and 'isContainer' in author:
            return author['isContainer']

        # Fall back to checking for group team account names
        if re.match(r'^\[[^\]]+]\\', display_name):
            return True

        return False

    def add_review(self, request_id: str, reviewer: Result) -> None:
        """
        Add a pull request review described by its TFS API response object to
        the merge request reviews table.
        """

        # Ignore project team container accounts (aggregate votes)
        if not self._is_container_account(reviewer, reviewer['uniqueName']):
            self._tables["merge_request_review"].append({
                'repo_name': str(self._repo_name),
                'merge_request_id': request_id,
                'reviewer': parse_unicode(reviewer['displayName']),
                'reviewer_username': parse_unicode(reviewer['uniqueName']),
                'vote': str(reviewer['vote'])
            })

    def add_thread_comments(self, request_id: str, thread: Result) -> None:
        """
        Add comments from a pull request code review comment thread described
        by its TFS API response object to the merge request notes or commit
        comments table.
        """

        if 'isDeleted' in thread and thread['isDeleted']:
            return

        for comment in thread['comments']:
            self.add_thread_comment(comment, request_id, thread)

    def add_thread_comment(self, comment: Result, request_id: str,
                           thread: Result) -> None:
        """
        Add a pull request code review comment described by its TFS API
        response object to the merge request notes or commit comments table.
        """

        author = comment['author']
        display_name = author['displayName']
        if 'authorDisplayName' in comment:
            display_name = comment['authorDisplayName']

        if self._is_container_account(author, display_name):
            return
        if 'isDeleted' in comment and comment['isDeleted']:
            return

        created_date = parse_utc_date(comment['publishedDate'])
        updated_date = parse_utc_date(comment['lastUpdatedDate'])
        if not self._is_newer(get_local_datetime(updated_date)):
            return

        if 'authorDisplayName' in comment or 'uniqueName' not in author:
            unique_name = display_name
        else:
            unique_name = author['uniqueName']

        parent_id = 0
        if 'parentId' in comment:
            parent_id = comment['parentId']
        elif 'parentCommentId' in comment:
            parent_id = comment['parentCommentId']

        note = {
            'repo_name': str(self._repo_name),
            'merge_request_id': request_id,
            'thread_id': str(thread['id']),
            'note_id': str(comment['id']),
            'parent_id': str(parent_id),
            'author': parse_unicode(display_name),
            'author_username': parse_unicode(unique_name),
            'comment': parse_unicode(comment['content']),
            'created_at': created_date,
            'updated_at': updated_date
        }

        # Determine whether to add as commit comment or request note
        if f'{self.PROPERTY}.ItemPath' in thread['properties']:
            self.add_commit_comment(note, thread['properties'])
        else:
            self._tables["merge_request_note"].append(note)

    def add_commit_comment(self, note: Dict[str, str], properties: Result) -> None:
        """
        Add a pull request code review file comment described by its incomplete
        note dictionary and the thread properties from the TFS API response
        to the commit comments table.
        """

        if f'{self.PROPERTY}.Position.PositionContext' in properties:
            context = properties[f'{self.PROPERTY}.Position.PositionContext']
            if context['$value'] == 'LeftBuffer':
                line_type = 'old'
            else:
                line_type = 'new'
        else:
            line_type = str(0)

        if f'{self.PROPERTY}.Position.StartLine' in properties:
            line = properties[f'{self.PROPERTY}.Position.StartLine']['$value']
        else:
            line = 0

        if f'{self.PROPERTY}.Position.EndLine' in properties:
            end_line = properties[f'{self.PROPERTY}.Position.EndLine']['$value']
        else:
            end_line = 0

        note.update({
            # Move creation and update date fields
            'created_date': note['created_at'],
            'updated_date': note['updated_at'],
            'file': properties[f'{self.PROPERTY}.ItemPath']['$value'],
            'line': str(line),
            'end_line': str(end_line),
            'line_type': line_type,
            'commit_id': properties['CodeReviewTargetCommit']['$value']
        })
        del note['created_at']
        del note['updated_at']
        self._tables["commit_comment"].append(note)

    def add_event(self, event: Result) -> None:
        """
        Add a push event from the TFS API to the VCS events table.
        """

        # Ignore incomplete/group/automated accounts
        if event['pushedBy']['uniqueName'].startswith('vstfs:///'):
            return

        event_date = parse_utc_date(event['date'])
        if not self._is_newer(get_local_datetime(event_date)):
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
                'user': parse_unicode(event['pushedBy']['displayName']),
                'username': parse_unicode(event['pushedBy']['uniqueName']),
                'email': str(0),
                'date': event_date
            })

    def add_team(self, team: Result) -> None:
        """
        Add team and team member data from the API to the associated tables.
        """

        team_name = parse_unicode(team['name'])
        self._tables["tfs_team"].append({
            'repo_name': str(self._repo_name),
            'team_name': team_name,
            'description': parse_unicode(team['description'])
        })

        for member in self.api.team_members(self.project_id, team['id']):
            self._tables["tfs_team_member"].append({
                'repo_name': str(self._repo_name),
                'team_name': team_name,
                'user': parse_unicode(member['displayName']),
                'username': parse_unicode(member['uniqueName'])
            })

        for sprint in self.api.sprints(self.project_id, team['id']):
            if sprint['attributes'].get('startDate') is not None:
                start_date = parse_utc_date(sprint['attributes']['startDate'])
            else:
                start_date = str(0)

            if sprint['attributes'].get('finishDate') is not None:
                end_date = parse_utc_date(sprint['attributes']['finishDate'])
            else:
                end_date = str(0)

            self._tables["tfs_sprint"].append({
                'repo_name': str(self._repo_name),
                'team_name': team_name,
                'sprint_name': parse_unicode(sprint['name']),
                'start_date': start_date,
                'end_date': end_date,
            })

    def add_work_item_revisions(self) -> None:
        """
        Add work item revision data from the API.
        """

        vsts_fields_path = Path('vsts_fields.json')
        if not vsts_fields_path.exists():
            logging.info('Skipping collection of work items; no fields known')
            return

        parsers = [
            String_Parser(), Int_Parser(), Date_Parser(), Unicode_Parser(),
            Decimal_Parser(), Tags_Parser(),
            Developer_Parser(self._tables)
        ]
        types = dict((parser.type, parser) for parser in parsers)

        with vsts_fields_path.open('r', encoding='utf-8') as vsts_fields_file:
            work_item_fields: Work_Item_Fields = json.load(vsts_fields_file)

        for properties in work_item_fields.values():
            if "field" in properties and isinstance(properties["field"], str):
                properties["fields"] = [properties["field"]]

        fields: Set[str] = {
            prop for props in work_item_fields.values() for prop in props["fields"]
        }

        from_date = self._update_trackers['tfs_update']
        work_item_revisions = self.api.work_item_revisions(fields=list(fields),
                                                           from_date=from_date)

        for revision in work_item_revisions:
            self._add_work_item_revision(revision, work_item_fields, types)

    def _add_work_item_revision(self, revision: Result,
                                work_item_fields: Work_Item_Fields,
                                types: Dict[str, Field_Parser]) -> None:
        row = {
            "issue_id": str(revision["id"]),
            "changelog_id": str(revision["rev"])
        }
        for target, properties in work_item_fields.items():
            parser = types[str(properties["type"])]
            for field in properties["fields"]:
                if field in revision["fields"]:
                    value = parser.parse(revision["fields"][field])
                    if value is not None:
                        row[target] = value
                    break

        self._tables["tfs_work_item"].append(row)
