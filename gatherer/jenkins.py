"""
Module for accessing Jenkins build information and starting jobs.

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

from abc import ABCMeta
from configparser import RawConfigParser
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, \
    Tuple, Union
from urllib.parse import quote, urlencode
from requests.auth import HTTPBasicAuth
from requests.models import Response
from .config import Configuration
from .request import Session

BaseUrl = Optional[Union[str, Dict[str, str]]]

class NoneMapping(Mapping[str, None]): # pylint: disable=no-init
    """
    An empty mapping that returns `None` for all key lookups.
    """

    def __getitem__(self, key: str) -> None:
        return None

    def __iter__(self) -> Iterator[str]:
        while False:
            yield

    def __len__(self) -> int:
        return 0

    def __contains__(self, key: object) -> bool:
        return False

    def __repr__(self) -> str:
        return 'NoneMapping()'

class Base(metaclass=ABCMeta):
    """
    Base Jenkins object.
    """

    DELETE_URL: Optional[str] = None

    def __init__(self, instance: 'Jenkins', base_url: BaseUrl,
                 exists: Optional[bool] = True) -> None:
        self._instance = instance

        # Allow API query parameters such as 'tree' and 'depth' to be passed
        # as a dict. The base URL should be in the parameter 'url', which is
        # removed from the query. Subclasses may also provide a default base
        # URL afterward.
        query: Dict[str, str] = {}
        if isinstance(base_url, dict):
            query = base_url.copy()
            base_url = query.pop('url', None)

        # Ensure the base URL ends in a slash for further suffixes
        if isinstance(base_url, str) and not base_url.endswith('/'):
            base_url = f'{base_url}/'

        self._base_url = base_url
        self._query = query
        self._data: Mapping[str, Any] = {}
        self._has_data = False
        self._exists = exists
        self._version: Optional[str] = None

    @property
    def base_url(self) -> str:
        """
        Retrieve the base (HTML) URL of this Jenkins object.
        """

        if self._base_url is None:
            raise ValueError('API URL unknown for this Jenkins object')

        return str(self._base_url)

    @property
    def query(self) -> Dict[str, str]:
        """
        Retrieve the query used to retrieve data for this Jenkins object.

        Returns a dictionary of query parameters which can be updated.
        """

        return self._query

    @query.setter
    def query(self, query: Dict[str, str]) -> None:
        """
        Replace the query used to retrieve data for this Jenkins object.
        """

        self._query = query

    def _retrieve(self) -> None:
        url = f'{self.base_url}api/json?{urlencode(self._query)}'
        request = self.instance.session.get(url, timeout=self.instance.timeout)
        self._version = request.headers.get('X-Jenkins', '')
        if Session.is_code(request, 'not_found'):
            self._exists = False
            self._data = NoneMapping()
        else:
            self._data = request.json()
            self._has_data = True
            self._exists = True

    @property
    def data(self) -> Mapping[str, Any]:
        """
        Retrieve the raw data from the API. The API is accessed if the data has
        not been retrieved before since the last invalidation or since the
        construction of this object.
        """

        if self._exists is not False and not self._has_data:
            self._retrieve()

        return self._data

    @property
    def has_data(self) -> bool:
        """
        Retrieve a boolean indicating whether we fetched data for the object.
        Returns `True` if and only if the current data is from the object's API
        endpoint itself. This property returns `False` if the data is from
        another API endpoint, e.g., a parent object, if the data has been
        invalidated or if the dat has not been retrieved at all.
        """

        return self._has_data

    @property
    def version(self) -> str:
        """
        Retrieve the version number of the Jenkins instance.

        If the version is not provided, then this is the empty string.
        """

        if self._version is None:
            if self._instance == self:
                self._version = ''
                self._retrieve()
            else:
                return self._instance.version

        return self._version

    def invalidate(self) -> None:
        """
        Ensure that we refresh the data for this object on next lookup.
        """

        self._has_data = False
        self._data = {}
        self._version = None

    @property
    def instance(self) -> 'Jenkins':
        """
        Retrieve the Jenkins instance to which this object belongs.
        """

        return self._instance

    @property
    def exists(self) -> bool:
        """
        Retrieve whether this object exists on the Jenkins instance.
        """

        if self._exists is None:
            self._exists = False
            self._retrieve()

        return self._exists

    def delete(self) -> None:
        """
        Delete the object from the Jenkins instance if possible.

        If the object cannot be deleted, then a `TypeError` or the appropriate
        request status is raised.
        """

        if self.DELETE_URL is None:
            raise TypeError("This object does not support deletion")

        url = f'{self.base_url}{self.DELETE_URL}'
        request = self.instance.session.post(url, timeout=self.instance.timeout)
        request.raise_for_status()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Base):
            return self.base_url == other.base_url

        return False

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self.exists

    def __hash__(self) -> int:
        return hash((self.instance, self.base_url))

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.base_url!r})'

class Jenkins(Base):
    """
    Jenkins instance.
    """

    def __init__(self, host: str, username: Optional[str] = None,
                 password: Optional[str] = None,
                 verify: Union[bool, str] = True) -> None:
        super().__init__(self, host)

        if username is not None and password is not None:
            auth: Optional[HTTPBasicAuth] = HTTPBasicAuth(username, password)
        else:
            auth = None

        self._session = Session(verify=verify, auth=auth)
        self.timeout: Optional[int] = None

        self._add_crumb_header()

    @classmethod
    def from_config(cls, config: RawConfigParser) -> 'Jenkins':
        """
        Create a Jenkins instance based on a settings from a 'jenkins' section
        that has been read by the configuration parser `config`.
        """

        host = config.get('jenkins', 'host')
        username: Optional[str] = config.get('jenkins', 'username')
        password: Optional[str] = config.get('jenkins', 'password')
        verify_config: str = config.get('jenkins', 'verify')
        verify: Union[bool, str] = verify_config
        if not Configuration.has_value(username):
            username = None
            password = None
        if not Configuration.has_value(verify_config):
            verify = False
        elif not Path(verify_config).exists():
            verify = True

        return cls(host, username=username, password=password, verify=verify)

    def _add_crumb_header(self) -> None:
        request = self._session.get(f'{self.base_url}crumbIssuer/api/json',
                                    timeout=3)
        if Session.is_code(request, 'not_found'):
            return

        request.raise_for_status()
        crumb_data: Dict[str, str] = request.json()
        headers = {crumb_data['crumbRequestField']: crumb_data['crumb']}
        self._session.headers.update(headers)

    @property
    def instance(self) -> 'Jenkins':
        return self

    @property
    def session(self) -> Session:
        """
        Retrieve the (authenticated) requests session.
        """

        return self._session

    @property
    def nodes(self) -> 'Nodes':
        """
        Retrieve the nodes linked to the Jenkins instance.
        """

        return Nodes(self)

    @property
    def jobs(self) -> List['Job']:
        """
        Retrieve a list of jobs on the Jenkins instance.
        """

        return [Job(self, **job) for job in self.data['jobs']]

    @property
    def views(self) -> List['View']:
        """
        Retrieve a list of views on the Jenkins instance.
        """

        return [View(self, **view) for view in self.data['views']]

    def get_job(self, name: str, url: BaseUrl = None) -> 'Job':
        """
        Retrieve a job from the Jenkins instance by its name.

        The optional parameter `url` may be used to provide a custom URL of
        the HTML page of the job, or a dictionary of query parameters.
        """

        if '/' in name:
            # Support workflow 'full project' job names
            workflow_name, pipeline_name = name.split('/', 1)
            workflow_job = Job(self, name=workflow_name, exists=None)
            return workflow_job.get_job(pipeline_name, url=url)

        return Job(self, name=name, url=url, exists=None)

    def get_view(self, name: str) -> 'View':
        """
        Retrieve a view from the Jenkins instance by its name.
        """

        return View(self, name=name, exists=None)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Jenkins):
            return self.base_url == other.base_url

        return False

    def __hash__(self) -> int:
        return hash(self.base_url)

class Nodes(Base, Sequence['Node']):
    """
    Collection of nodes linked to the Jenkins instance.
    """

    def __init__(self, instance: Jenkins) -> None:
        url = f'{instance.base_url}computer/'
        super().__init__(instance, url, exists=True)
        self.instance.session.headers.update({'Accept-Language': 'en'})
        self._nodes: Optional[List['Node']] = None

    @property
    def nodes(self) -> List['Node']:
        """
        Retrieve all the linked nodes.
        """

        if self._nodes is None:
            self._nodes = [
                Node(self.instance, **node) for node in self.data['computer']
            ]

        return self._nodes

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Nodes):
            return self.base_url == other.base_url

        return False

    def __getitem__(self, index: Any) -> Any:
        return self.nodes[index]

    def __len__(self) -> int:
        return len(self.nodes)

class Node(Base):
    """
    Computer node linked to a Jenkins instance.
    """

    def __init__(self, instance: Jenkins, **kwargs: Any) -> None:
        display_name = str(kwargs.get('displayName', ''))
        if display_name == '':
            raise ValueError('Display name must be provided')

        if display_name == "master":
            name = f"({display_name})"
        elif display_name == "Built-In Node":
            name = "(built-in)"
        else:
            name = display_name

        url = f'{instance.base_url}computer/{quote(name)}'
        super().__init__(instance, url, exists=True)
        self._name = name
        self._data = kwargs

    @property
    def name(self) -> str:
        """
        Retrieve the name of the node.
        """

        return self._name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Node):
            return self.instance == other.instance and self.name == other.name

        return False

class View(Base):
    """
    View on a Jenkins instance.
    """

    DELETE_URL = 'doDelete'

    def __init__(self, instance: Jenkins, name: str = '', url: BaseUrl = None,
                 exists: Optional[bool] = True, **kwargs: Any) -> None:
        if name == '':
            raise ValueError('Name must be provided')

        super().__init__(instance, url, exists=exists)
        if self._base_url is None:
            self._base_url = f'{instance.base_url}view/{quote(name)}'

        self._name = name
        self._data = kwargs

    @property
    def name(self) -> str:
        """
        Retrieve the name of the view.
        """

        return self._name

    @property
    def jobs(self) -> List['Job']:
        """
        Retrieve the jobs in this view.
        """

        return [Job(self.instance, **job) for job in self.data['jobs']]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, View):
            return self.instance == other.instance and self.name == other.name

        return False

class Job(Base):
    """
    Job on a Jenkins instance.
    """

    DELETE_URL = 'doDelete'

    def __init__(self, instance: Union[Jenkins, 'Job'], name: str = '',
                 url: BaseUrl = None, exists: Optional[bool] = True,
                 **kwargs: Any) -> None:
        if name == '':
            raise ValueError('Name must be provided')

        # Collect actual instance for multibranch workflow jobs
        base = instance
        if isinstance(instance, Job):
            instance = instance.instance

        super().__init__(instance, url, exists=exists)
        if self._base_url is None:
            self._base_url = f'{base.base_url}job/{quote(name)}/'

        self._name = name
        self._data = kwargs
        self._last_builds: Dict[str, Build] = {}

    @property
    def name(self) -> str:
        """
        Retrieve the job name.
        """

        return self._name

    @property
    def builds(self) -> List['Build']:
        """
        Retrieve the builds.
        """

        if 'builds' not in self.data:
            return []

        return [Build(self, **build) for build in self.data['builds']]

    @property
    def jobs(self) -> List['Job']:
        """
        Retrieve the jobs of a multibranch pipeline workflow.

        The list of jobs never contains this job itself. If this is not
        a multibranch pipeline job, then an empty list is returned.
        """

        if 'jobs' not in self.data:
            return []

        return [Job(self, **job) for job in self.data['jobs']]

    def get_job(self, name: str, url: BaseUrl = None) -> 'Job':
        """
        Retrieve a job of a multibranch pipeline workflow by its pipeline name.

        The optional parameter `url` may be used to provide a custom URL of
        the HTML page of the job, or a dictionary of query parameters.
        """

        return Job(self, name=name, url=url, exists=None)

    def _make_last_build(self, name: str) -> 'Build':
        if name not in self._last_builds:
            if self.has_data and name in self.data:
                if self.data[name] is None:
                    self._last_builds[name] = Build(self, exists=False)
                else:
                    self._last_builds[name] = Build(self, **self.data[name])
            else:
                url = f'{self.base_url}{name}/'
                self._last_builds[name] = Build(self, url=url, exists=None)

        return self._last_builds[name]

    @property
    def last_build(self) -> 'Build':
        """
        Retrieve the last build.
        """

        return self._make_last_build('lastBuild')

    @property
    def last_completed_build(self) -> 'Build':
        """
        Retrieve the last completed build.
        """

        return self._make_last_build('lastCompletedBuild')

    @property
    def last_failed_build(self) -> 'Build':
        """
        Retrieve the last failed build.
        """

        return self._make_last_build('lastFailedBuild')

    @property
    def last_stable_build(self) -> 'Build':
        """
        Retrieve the last stable build.
        """

        return self._make_last_build('lastStableBuild')

    @property
    def last_successful_build(self) -> 'Build':
        """
        Retrieve the last successful build.
        """

        return self._make_last_build('lastSuccessfulBuild')

    @property
    def last_unstable_build(self) -> 'Build':
        """
        Retrieve the last unstable build.
        """

        return self._make_last_build('lastUnstableBuild')

    @property
    def last_unsuccessful_build(self) -> 'Build':
        """
        Retrieve the last unsuccessful build.
        """

        return self._make_last_build('lastUnsuccessfulBuild')

    @property
    def next_build_number(self) -> int:
        """
        Retrieve the next build number.
        """

        return int(self.data['nextBuildNumber'])

    def get_build(self, number: int) -> 'Build':
        """
        Retrieve a previous build based on its number.
        """

        exists: Optional[bool] = None
        if self.has_data:
            numbers = [build['number'] for build in self.data['builds']]
            exists = number in numbers

        return Build(self, number=number, exists=exists)

    def get_last_branch_build(self, branch: str) -> \
            Tuple[Optional['Build'], Optional[Dict[str, Any]]]:
        """
        Retrieve the latest build of this job for the given `branch`.

        The returned tuple contains the `Build` object and the branch build data
        which is separate from the build data itself.

        If the job or its builds do not exist, then a `ValueError` is raised.

        If the branch build cannot be found, then a tuple of `None` and `None`
        is returned.
        """

        # Retrieve the latest build job. This may be a build for another
        # branch, so we check the builds by branch name on this build.
        # The job may have no builds in which case we cannot check stability.
        build = self.last_build
        if not build.exists:
            raise ValueError('Jenkins job or its builds could not be found')

        for action in build.data['actions']:
            if 'buildsByBranchName' in action:
                build_data: Dict[str, Dict[str, Any]] = action['buildsByBranchName']
                # Check if there has been a build for the branch.
                if branch not in build_data:
                    return None, None

                # Retrieve the build job that actually built this branch.
                build_number = build_data[branch]['buildNumber']
                if build_number != build.number:
                    build = self.get_build(build_number)

                return build, build_data[branch]

        return None, None

    @property
    def default_parameters(self) -> List[Dict[str, str]]:
        """
        Retrieve a list of dictionaries containing a 'name' and 'value'
        entry for every parameter defined for a parameterized job.
        """

        parameters: List[Dict[str, str]] = []
        for action in self.data['actions']:
            if 'parameterDefinitions' in action:
                for parameter in action['parameterDefinitions']:
                    value = str(parameter['defaultParameterValue']['value'])
                    parameters.append({
                        "name": str(parameter['name']),
                        "value": value
                    })

                return parameters

        return parameters

    def build(self, parameters: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = None,
              token: Optional[str] = None) -> Response:
        """
        Build the job. The given `parameters` may be a list of dictionaries
        containing parameter attributes, or a dictionary of parameter key-value
        pairs. If it is `None` (default), then no parameters are provided to
        the build. The `token` is a remote trigger token for authenticating
        specifically for this job.
        """

        url = f'{self.base_url}build'
        params = {}
        data = None
        if token is not None:
            params['token'] = token

        if isinstance(parameters, list):
            data = {"json": json.dumps({"parameter": parameters})}
        elif isinstance(parameters, dict):
            url = f'{self.base_url}buildWithParameters'
            params.update(parameters)

        return self.instance.session.post(url, params=params, data=data,
                                          timeout=self.instance.timeout)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Job):
            return self.instance == other.instance and self.name == other.name

        return False

class Build(Base):
    """
    Build information of a certain job on a Jenkins instance.
    """

    DELETE_URL = 'doDelete'

    def __init__(self, job: Job, number: Optional[int] = None,
                 url: BaseUrl = None, exists: Optional[bool] = True,
                 **kwargs: Any) -> None:
        super().__init__(job.instance, url, exists=exists)
        if self._base_url is None:
            self._base_url = f'{job.base_url}{number}/'

        self._job = job
        self._number = number
        self._data = kwargs

    @property
    def job(self) -> Job:
        """
        Retrieve the job for this build.
        """

        return self._job

    @property
    def number(self) -> int:
        """
        Retrieve the build number.
        """

        if self._number is None:
            self._number = int(self.data['number'])
            if self._number is None:
                return 0

        return self._number

    @property
    def result(self) -> Optional[str]:
        """
        Retrieve the build result.
        """

        return self.data['result']

    @property
    def building(self) -> Optional[bool]:
        """
        Retrieve whether this build is currently building.
        """

        return self.data['building']

    def _related(self, other: 'Build') -> bool:
        return self.exists and other.exists and self.job == other.job

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Build):
            return self._related(other) and self.number == other.number

        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Build) and self._related(other):
            return self.number < other.number

        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Build) and self._related(other):
            return self.number > other.number

        return NotImplemented

    def __lte__(self, other: object) -> bool:
        if isinstance(other, Build) and self._related(other):
            return self.number <= other.number

        return NotImplemented

    def __gte__(self, other: object) -> bool:
        if isinstance(other, Build) and self._related(other):
            return self.number >= other.number

        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.job, self.number))

    def __repr__(self) -> str:
        if self.exists and self.has_data:
            return f'Build({self.job!r}, number={self.number!r})'

        return super().__repr__()
