"""
Module for accessing Jenkins build information and starting jobs.
"""

from builtins import object
from abc import ABCMeta
from collections import Mapping
import json
from future.utils import with_metaclass
import requests
from requests.auth import HTTPBasicAuth
from requests.utils import quote

class NoneMapping(Mapping): # pylint: disable=no-init
    """
    An empty mapping that returns `None` for all key lookups.
    """

    def __getitem__(self, key):
        return None

    def __iter__(self):
        while False:
            yield None

    def __len__(self):
        return 0

    def __contains__(self, key):
        return False

    def __repr__(self):
        return 'NoneMapping()'

class Base(with_metaclass(ABCMeta, object)):
    """
    Base Jenkins object.
    """

    def __init__(self, instance, base_url, exists=True):
        self._instance = instance

        if not base_url.endswith('/'):
            base_url += '/'

        self._base_url = base_url
        self._data = None
        self._has_data = False
        self._exists = exists

    @property
    def base_url(self):
        """
        Retrieve the base (HTML) URL of this Jenkins object.
        """

        return self._base_url

    @property
    def data(self):
        """
        Retrieve the raw data from the API.
        """

        if self._exists and not self._has_data:
            request = self.instance.session.get(self.base_url + 'api/json')
            if request.status_code == requests.codes['not_found']:
                self._exists = False
                self._data = NoneMapping()
            else:
                self._data = request.json()
                self._has_data = True

        return self._data

    @property
    def has_data(self):
        """
        Retrieve a boolean indicating whether we fetched data for the object.
        Returns `True` if and only if the current data is from the object's API
        endpoint itself. This property returns `False` if the data is from
        another API endpoint, e.g., a parent object, if the data has been
        invalidated or if the dat has not been retrieved at all.
        """

        return self._has_data

    def invalidate(self):
        """
        Ensure that we refresh the data for this object on next lookup.
        """

        self._has_data = False
        self._data = None

    @property
    def instance(self):
        """
        Retrieve the Jenkins instance to which this object belongs.
        """

        return self._instance

    @property
    def exists(self):
        """
        Retrieve whether this object exists on the Jenkins instance.
        """

        return self._exists

    def __eq__(self, other):
        if isinstance(other, Base):
            return self.base_url == other.base_url

        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __nonzero__(self):
        return self.exists

    def __hash__(self):
        return hash((self.instance, self.base_url))

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.base_url)

class Jenkins(Base):
    """
    Jenkins instance.
    """

    def __init__(self, host, username=None, password=None, verify=True):
        super(Jenkins, self).__init__(self, host)
        self._session = requests.Session()
        self._session.verify = verify
        if username is not None:
            self._session.auth = HTTPBasicAuth(username, password)

        self._add_crumb_header()

    def _add_crumb_header(self):
        request = self._session.get(self.base_url + 'crumbIssuer/api/json')
        if request.status_code == requests.codes['not_found']:
            return

        request.raise_for_status()
        crumb_data = request.json()
        headers = {crumb_data['crumbRequestField']: crumb_data['crumb']}
        self._session.headers.update(headers)

    @property
    def instance(self):
        return self

    @property
    def session(self):
        """
        Retrieve the (authenticated) requests session.
        """

        return self._session

    @property
    def jobs(self):
        """
        Retrieve the jobs on the Jenkins instance.
        """

        return [Job(self, **job) for job in self.data['jobs']]

    @property
    def views(self):
        """
        Retrieve the views on the Jenkins instance.
        """

        return [View(self, **view) for view in self.data['views']]

    def __eq__(self, other):
        if isinstance(other, Jenkins):
            return self.base_url == other.base_url

        return False

    def __hash__(self):
        return hash(self.base_url)

class View(Base):
    """
    View on a Jenkins instance.
    """

    def __init__(self, instance, name=None, url=None, **kwargs):
        if name is None:
            raise ValueError('Name must be provided')
        if url is None:
            url = '{}view/{}'.format(instance.base_url, quote(name))

        super(View, self).__init__(instance, url)
        self._name = name
        self._data = kwargs

    @property
    def name(self):
        """
        Retrieve the name of the view.
        """

        return self._name

    @property
    def jobs(self):
        """
        Retrieve the jobs in this view.
        """

        return [Job(self.instance, **job) for job in self.data['jobs']]

    def __eq__(self, other):
        if isinstance(other, View):
            return self.instance == other.instance and self.name == other.name

        return False

class Job(Base):
    """
    Job on a Jenkins instance.
    """

    def __init__(self, instance, name=None, url=None, **kwargs):
        if name is None:
            raise ValueError('Name must be provided')
        if url is None:
            url = '{}job/{}/'.format(self.instance.base_url, quote(name))

        super(Job, self).__init__(instance, url)
        self._name = name
        self._data = kwargs
        self._last_builds = {}

    @property
    def name(self):
        """
        Retrieve the job name.
        """

        return self._name

    @property
    def builds(self):
        """
        Retrieve the builds.
        """

        return [Build(self, **build) for build in self.data['builds']]

    def _make_last_build(self, name):
        if name not in self._last_builds:
            if self.has_data:
                if self.data[name] is None:
                    self._last_builds[name] = Build(self, exists=False)
                else:
                    self._last_builds[name] = Build(self, **self.data[name])
            else:
                url = '{}{}/'.format(self.base_url, name)
                self._last_builds[name] = Build(self, url=url)

        return self._last_builds[name]

    @property
    def last_build(self):
        """
        Retrieve the last build.
        """

        return self._make_last_build('lastBuild')

    @property
    def last_completed_build(self):
        """
        Retrieve the last completed build.
        """

        return self._make_last_build('lastCompletedBuild')

    @property
    def last_failed_build(self):
        """
        Retrieve the last failed build.
        """

        return self._make_last_build('lastFailedBuild')

    @property
    def last_stable_build(self):
        """
        Retrieve the last stable build.
        """

        return self._make_last_build('lastStableBuild')

    @property
    def last_successful_build(self):
        """
        Retrieve the last successful build.
        """

        return self._make_last_build('lastSuccessfulBuild')

    @property
    def last_unstable_build(self):
        """
        Retrieve the last unstable build.
        """

        return self._make_last_build('lastUnstableBuild')

    @property
    def last_unsuccessful_build(self):
        """
        Retrieve the last unsuccessful build.
        """

        return self._make_last_build('lastUnsuccessfulBuild')

    @property
    def next_build_number(self):
        """
        Retrieve the next build number.
        """

        return self.data['nextBuildNumber']

    def build(self, parameters=None, token=None):
        """
        Build the job. The given `parameters` may be a list of dictionaries
        containing parameter attributes, or a dictionary of parameter key-value
        pairs. If it is `None` (default), then no parameters are provided to
        the build. The `token` is a remote trigger token for authenticating
        specifically for this job.
        """

        url = self.base_url + 'build'
        params = {}
        data = None
        if token is not None:
            params['token'] = token

        if isinstance(parameters, list):
            data = {"json": json.dumps({"parameter": parameters})}
        elif isinstance(parameters, dict):
            url = self.base_url + 'buildWithParameters'
            params.update(parameters)
        elif parameters is not None:
            raise TypeError('Parameters must be list or dict')

        return self.instance.session.post(url, params=params, data=data)

    def __eq__(self, other):
        if isinstance(other, Job):
            return self.instance == other.instance and self.name == other.name

        return False

class Build(Base):
    """
    Build information of a certain job on a Jenkins instance.
    """

    def __init__(self, job, number=None, url=None, exists=True, **kwargs):
        if url is None:
            url = '{}{}/'.format(job.base_url, number, exists=exists)
        super(Build, self).__init__(job.instance, url)
        self._job = job
        self._number = number
        self._data = kwargs

    @property
    def job(self):
        """
        Retrieve the job for this build.
        """

        return self._job

    @property
    def number(self):
        """
        Retrieve the build number.
        """

        if self._number is None:
            self._number = self.data['number']

        return self._number

    def _related(self, other):
        if isinstance(other, Build):
            return self.exists and other.exists and self.job == other.job

        return False

    def __eq__(self, other):
        return self._related(other) and self.number == other.number

    def __lt__(self, other):
        if self._related(other):
            return self.number < other.number

        return NotImplemented

    def __gt__(self, other):
        if self._related(other):
            return self.number > other.number

        return NotImplemented

    def __lte__(self, other):
        if self._related(other):
            return self.number <= other.number

        return NotImplemented

    def __gte__(self, other):
        if self._related(other):
            return self.number >= other.number

        return NotImplemented

    def __hash__(self):
        return hash((self.job, self.number))

    def __repr__(self):
        if self.exists and self.has_data:
            return 'Build({!r}, number={!r})'.format(self.job, self.number)

        return super(Build, self).__repr__()
