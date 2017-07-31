"""
Module for accessing Jenkins build information and starting jobs.
"""

from builtins import object
from abc import ABCMeta
import json
from future.utils import with_metaclass
import requests
from requests.auth import HTTPBasicAuth
from requests.utils import quote

class Base(with_metaclass(ABCMeta, object)):
    """
    Base Jenkins object.
    """

    def __init__(self, instance, base_url):
        self._instance = instance

        if not base_url.endswith('/'):
            base_url += '/'

        self._base_url = base_url
        self._data = None
        self._has_data = False

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

        if not self._has_data:
            request = self.instance.session.get(self.base_url + 'api/json')
            self._data = request.json()
            self._has_data = True

        return self._data

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

    @property
    def last_build(self):
        """
        Retrieve the last build, or `None`.
        """

        return Build(self, **self.data['lastBuild'])

    @property
    def last_completed_build(self):
        """
        Retrieve the last completed build.
        """

        return Build(self.instance, **self.data['lastCompletedBuild'])

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

class Build(Base):
    """
    Build information of a certain job on a Jenkins instance.
    """

    def __init__(self, job, number=None, url=None, **kwargs):
        if number is None:
            raise ValueError('Number is required')
        if url is None:
            url = '{}{}/'.format(job.base_url, number)
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

        return self._number
