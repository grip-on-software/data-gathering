"""
Tests for module for accessing Jenkins build information.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from configparser import RawConfigParser
from typing import Any, Optional, Tuple
import unittest
from unittest.mock import patch
from requests.auth import HTTPBasicAuth
import requests_mock
from gatherer.jenkins import Base, Build, Jenkins, Job, Nodes, Node, \
    NoneMapping, View

class NoneMappingTest(unittest.TestCase):
    """
    Tests for an empty mapping.
    """

    def test_properties(self) -> None:
        """
        Test various properties of the mapping.
        """

        mapping = NoneMapping()
        self.assertIsNone(mapping['thing'])
        with self.assertRaises(StopIteration):
            next(iter(mapping))

        self.assertEqual(len(mapping), 0)
        self.assertNotIn('key', mapping)
        self.assertEqual(repr(mapping), 'NoneMapping()')

def _setup_jenkins(**kwargs: Any) -> Tuple[Jenkins, requests_mock.Adapter]:
    # Default protocol to use in our adapter
    protocol = 'http+mock://'

    # Create or obtain the Jenkins instance
    host: Optional[str] = None
    if 'jenkins' in kwargs:
        jenkins = kwargs.pop('jenkins')
    else:
        host = str(kwargs.pop('host', f'{protocol}jenkins.test'))
        jenkins = Jenkins(host)

    # Set up adapter with crumb issuer route (just route it to a 404)
    adapter = requests_mock.Adapter()
    adapter.register_uri('GET', '/crumbIssuer/api/json', status_code=404)

    # Extend to protocol matching
    prefix = host
    if prefix is not None and prefix.startswith(protocol):
        prefix = protocol

    jenkins.mount(adapter, prefix=prefix)
    return jenkins, adapter

class BaseTest(unittest.TestCase):
    """
    Tests for base Jenkins object.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()
        self.base = Base(self.jenkins, self.jenkins.base_url)

    def test_base_url(self) -> None:
        """
        Test retrieving the base URL.
        """

        self.assertEqual(self.base.base_url, 'http+mock://jenkins.test/')

        base = Base(self.jenkins, None)
        with self.assertRaises(ValueError):
            self.assertIsNone(base.base_url)

        params = Base(self.jenkins, {
            'depth': '2',
            'url': 'http+mock://jenkins.test/base/url/'
        })
        self.assertEqual(params.base_url, 'http+mock://jenkins.test/base/url/')

    def test_query(self) -> None:
        """
        Test retrieving the query parameters.
        """

        self.assertEqual(self.base.query, {})

        params = Base(self.jenkins, {
            'depth': '2',
            'url': 'http+mock://jenkins.test/base/url/'
        })
        self.assertEqual(params.query, {'depth': '2'})

        # Query setter
        params.query = {'url': 'really-important'}
        self.assertEqual(params.query, {'url': 'really-important'})

    def test_data(self) -> None:
        """
        Test retrieving the raw data from the API.
        """

        self.assertFalse(self.base.has_data)

        matcher = self.adapter.register_uri('GET', '/api/json',
                                            json={'foo': 'bar'})
        self.assertEqual(self.base.data, {'foo': 'bar'})

        self.assertTrue(self.base.has_data)
        self.assertTrue(matcher.called_once)

        self.adapter.reset()
        matcher = self.adapter.register_uri('GET', '/api/json', status_code=404)

        # The data is still cached, so any issues upstream do not affect us yet
        self.assertEqual(self.base.data, {'foo': 'bar'})
        self.assertFalse(matcher.called)

        self.base.invalidate()

        self.assertEqual(self.base.data, NoneMapping())
        self.assertTrue(matcher.called_once)

    def test_version(self) -> None:
        """
        Test retrieving the version number of the Jenkins instance.
        """

        matcher = self.adapter.register_uri('GET', '/api/json',
                                            headers={'X-Jenkins': '1.2.3'},
                                            json={'foo': 'bar'})
        self.assertEqual(self.base.version, '1.2.3')

        # The version remains cached.
        self.assertEqual(self.base.version, '1.2.3')
        self.assertTrue(matcher.called_once)

    def test_instance(self) -> None:
        """
        Test retrieving the Jenkins instance.
        """

        self.assertEqual(self.base.instance, self.jenkins)
        self.assertEqual(self.jenkins.instance, self.jenkins)

    def test_exists(self) -> None:
        """
        Test retrieving whether the object exists on the Jenkins instance.
        """

        matcher = self.adapter.register_uri('GET', '/api/json',
                                            json={'foo': 'bar'})

        # By default, the object is assumed to exist.
        self.assertTrue(self.base.exists)
        self.assertFalse(matcher.called)

        base = Base(self.jenkins, self.jenkins.base_url, exists=None)

        # The existence is cached.
        self.assertTrue(base.exists)
        self.assertTrue(matcher.called_once)

        base.invalidate()
        matcher = self.adapter.register_uri('GET', '/api/json', status_code=404)
        self.assertFalse(base.exists)

    def test_delete(self) -> None:
        """
        Test deleting the object from the Jenkins instance.
        """

        with self.assertRaises(TypeError):
            self.base.delete()

        with patch.object(Base, 'DELETE_URL', new='doDelete'):
            matcher = self.adapter.register_uri('POST', '/doDelete')
            self.base.delete()
            self.assertTrue(matcher.called_once)

    def test_comparison(self) -> None:
        """
        Test rich comparison equality, hash and other special methods.
        """

        same = Base(self.jenkins, 'http+mock://jenkins.test/')
        other = Base(self.jenkins, 'http+mock://other.test')
        self.assertTrue(self.base == same)
        self.assertFalse(self.base == other)
        self.assertFalse(self.base == 'http+mock://jenkins.test/')

        self.assertFalse(self.base != same)
        self.assertTrue(self.base != other)
        self.assertTrue(self.base != 'http+mock://jenkins.test/')

        self.assertTrue(self.base)

        invalid = Base(self.jenkins, 'http+mock://jenkins.test/', exists=False)
        self.assertFalse(invalid)

        self.assertEqual(hash(self.base),
                         hash(('http+mock://jenkins.test/',) * 2))

        self.assertEqual(repr(self.base), "Base('http+mock://jenkins.test/')")

class JenkinsTest(unittest.TestCase):
    """
    Tests for Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()

    def test_from_config(self) -> None:
        """
        Test creating a Jenkins instance based on settings.
        """

        config = RawConfigParser()
        config.add_section('jenkins')
        config.set('jenkins', 'host', 'https+mock://config.test')
        config.set('jenkins', 'username', '-')
        config.set('jenkins', 'password', '-')
        config.set('jenkins', 'verify', '0')
        raw = Jenkins.from_config(config)
        _setup_jenkins(jenkins=raw)
        self.assertEqual(raw.base_url, 'https+mock://config.test/')
        self.assertFalse(raw.session.verify)

        # Test verification
        config.set('jenkins', 'username', 'jenkinsuser')
        config.set('jenkins', 'password', 'jenkinspass')
        config.set('jenkins', 'verify', 'test/sample/invalid/path')
        auth = Jenkins.from_config(config)
        _setup_jenkins(jenkins=auth)
        self.assertTrue(auth.session.verify)
        self.assertEqual(auth.session.auth,
                         HTTPBasicAuth('jenkinsuser', 'jenkinspass'))

        # Test certificate verification and crumb token retrieval
        config.set('jenkins', 'verify', 'certs/README.md')
        verify = Jenkins.from_config(config)
        _, adapter = _setup_jenkins(jenkins=verify)
        adapter.register_uri('GET', '/crumbIssuer/api/json', json={
            'crumbRequestField': 'X-Crumb',
            'crumb': 'my-token'
        })
        self.assertEqual(verify.session.verify, 'certs/README.md')
        self.assertEqual(verify.session.headers['X-Crumb'], 'my-token')

    def test_properties(self) -> None:
        """
        Test retrieving properties of the Jenkins instance.
        """

        data = {
            'jobs': [
                {
                    'name': 'some-job',
                    'builds': []
                }
            ],
            'views': [
                {
                    'name': 'MyView',
                    'jobs': []
                }
            ]
        }
        matcher = self.adapter.register_uri('GET', '/api/json', json=data)

        self.assertEqual(self.jenkins.nodes.instance, self.jenkins)
        self.assertEqual(self.jenkins.jobs, [Job(self.jenkins, name='some-job',
                                                 builds=[])])
        self.assertEqual(self.jenkins.views, [View(self.jenkins, name='MyView',
                                                   jobs=[])])

        self.assertTrue(matcher.called_once)

        # Test comparison and hash functions
        self.assertTrue(self.jenkins == Jenkins('http+mock://jenkins.test/'))
        self.assertFalse(self.jenkins == Jenkins('http://other.test'))
        self.assertFalse(self.jenkins == 'http+mock://jenkins.test/')
        self.assertEqual(hash(self.jenkins), hash('http+mock://jenkins.test/'))

    def test_get_job(self) -> None:
        """
        Test retrieving a job from the Jenkins instance.
        """

        job = Job(self.jenkins, name='foo')
        self.assertEqual(self.jenkins.get_job('foo'), job)
        self.assertEqual(self.jenkins.get_job('foo/bar'), Job(job, name='bar'))

        query = {'tree': 'builds[number]'}
        self.assertEqual(self.jenkins.get_job('builder', url=query).query,
                         query)

    def test_get_view(self) -> None:
        """
        Test retrieving a view from the Jenkins instance.
        """

        self.assertEqual(self.jenkins.get_view('MyView'),
                         View(self.jenkins, name='MyView'))

class NodesTest(unittest.TestCase):
    """
    Tests for collection of nodes linked to a Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()
        self.nodes = Nodes(self.jenkins)

        data = {
            'computer': [
                {'displayName': 'Built-In Node'},
                {'displayName': 'Remote'}
            ]
        }
        self.adapter.register_uri('GET', '/computer/api/json', json=data)

    def test_nodes(self) -> None:
        """
        Test retrieving all the linked nodes.
        """

        self.assertEqual(self.nodes.nodes, [
            Node(self.jenkins, displayName='Built-In Node'),
            Node(self.jenkins, displayName='Remote')
        ])

    def test_comparison(self) -> None:
        """
        Test comparison and accessor methods of the nodes.
        """

        self.assertTrue(self.nodes == Nodes(Jenkins('http+mock://jenkins.test/')))
        self.assertFalse(self.nodes == Nodes(Jenkins('http://other.test/')))
        self.assertFalse(self.nodes == 'http+mock://jenkins.test/computer/')

        self.assertEqual(self.nodes[0],
                         Node(self.jenkins, displayName='Built-In Node'))
        self.assertEqual(len(self.nodes), 2)
        self.assertEqual(hash(self.nodes),
                         hash('http+mock://jenkins.test/computer/'))

class NodeTest(unittest.TestCase):
    """
    Tests for computer node linked to a Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins = _setup_jenkins()[0]
        self.node = Node(self.jenkins, displayName='Test')

    def test_name(self) -> None:
        """
        Test retrieving the name of the node.
        """

        self.assertEqual(self.node.name, 'Test')
        self.assertEqual(Node(self.jenkins, displayName='(weird name!)').name,
                         '(weird name!)')
        with self.assertRaises(ValueError):
            self.assertEqual(Node(self.jenkins).name, '')
        self.assertEqual(Node(self.jenkins, displayName='master').name,
                         '(master)')
        self.assertEqual(Node(self.jenkins, displayName='Built-In Node').name,
                         '(built-in)')

    def test_comparison(self) -> None:
        """
        Test comparison method of the node.
        """

        self.assertTrue(self.node == Node(Jenkins('http+mock://jenkins.test/'),
                                          displayName='Test'))
        self.assertFalse(self.node == Node(Jenkins('http://other.test/'),
                                           displayName='Test'))
        self.assertFalse(self.node == Node(self.jenkins, displayName='Other'))
        self.assertFalse(self.node == 'http+mock://jenkins.test/computer/Test/')
        self.assertEqual(hash(self.node),
                         hash('http+mock://jenkins.test/computer/Test/'))

class ViewTest(unittest.TestCase):
    """
    Tests for view on a Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()
        self.view = View(self.jenkins, name='MyTestView')

    def test_name(self) -> None:
        """
        Test retrieving the name of the view.
        """

        self.assertEqual(self.view.name, 'MyTestView')
        with self.assertRaises(ValueError):
            self.assertEqual(View(self.jenkins).name, '')

    def test_jobs(self) -> None:
        """
        Test retrieving the jobs in the view.
        """

        data = {
            'jobs': [
                {'name': 'job-1'},
                {'name': 'job-2'}
            ]
        }
        self.adapter.register_uri('GET', '/view/MyTestView/api/json', json=data)
        self.assertEqual(self.view.jobs, [
            Job(self.jenkins, name='job-1'), Job(self.jenkins, name='job-2')
        ])

    def test_comparison(self) -> None:
        """
        Test comparison method of the view.
        """

        self.assertTrue(self.view == View(Jenkins('http+mock://jenkins.test/'),
                                          url='http+mock://jenkins.test/view/MyTestView',
                                          name='MyTestView'))
        self.assertFalse(self.view == View(Jenkins('http://other.test/'),
                                           name='MyTestView'))
        self.assertFalse(self.view == View(self.jenkins, name='OtherView'))
        self.assertFalse(self.view == 'http+mock://jenkins.test/view/MyTestView/')
        self.assertEqual(hash(self.view),
                         hash('http+mock://jenkins.test/view/MyTestView/'))

class JobTest(unittest.TestCase):
    """
    Tests for job on a Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()
        self.job = Job(self.jenkins, name='test-job')

    def test_name(self) -> None:
        """
        Test retrieving the name of the job.
        """

        self.assertEqual(self.job.name, 'test-job')
        with self.assertRaises(ValueError):
            self.assertEqual(Job(self.jenkins).name, '')

    def test_base(self) -> None:
        """
        Test retrieving the parent of a multibranch pipeline job.
        """

        self.assertIsNone(self.job.base)
        child = Job(self.job, name='branch')
        self.assertEqual(child.base, self.job)

    def test_builds(self) -> None:
        """
        Test retrieving the builds.
        """

        data = {
            'builds': [
                {'number': 1},
                {'number': 2}
            ]
        }
        self.adapter.register_uri('GET', '/job/test-job/api/json', json=data)
        self.assertEqual(self.job.builds, [
            Build(self.job, number=1), Build(self.job, number=2)
        ])

        job = Job(self.jenkins, name='limited', url={
            'url': 'http+mock://jenkins.test/job/limited',
            'tree': 'name'
        })
        self.adapter.register_uri('GET', '/job/limited/api/json',
                                  json={'name': 'limited'})
        self.assertEqual(job.builds, [])

    def test_jobs(self) -> None:
        """
        Test retrieving the jobs of a multibranch pipeline workflow.
        """

        data = {
            'jobs': [
                {'name': 'child'},
                {'name': 'branch'}
            ]
        }
        self.adapter.register_uri('GET', '/job/test-job/api/json', json=data)
        self.assertEqual(self.job.jobs, [
            Job(self.job, name='child'), Job(self.job, name='branch')
        ])

        job = Job(self.jenkins, name='limited', url={
            'url': 'http+mock://jenkins.test/job/limited',
            'tree': 'builds'
        })
        self.adapter.register_uri('GET', '/job/limited/api/json',
                                  json={'builds': []})
        self.assertEqual(job.jobs, [])

    def test_get_job(self) -> None:
        """
        Test retrieving a job of a multibranch pipeline workflow by name.
        """

        self.assertEqual(self.job.get_job('bar'), Job(self.job, name='bar'))

    def test_build_properties(self) -> None:
        """
        Test retrieving builds by their status of being the last of a type.
        """

        self.assertEqual(self.job.last_build.base_url,
                         'http+mock://jenkins.test/job/test-job/lastBuild/')

        data = {
            'lastBuild': {'number': 42},
            'lastCompletedBuild': {'number': 41},
            'lastFailedBuild': {'number': 40},
            'lastStableBuild': None,
            'lastSuccessfulBuild': {'number': 32},
            'lastUnstableBuild': {'number': 41},
            'nextBuildNumber': 43
        }
        self.adapter.register_uri('GET', '/job/test-job/api/json', json=data)

        # Previous job build state remains cached.
        self.assertEqual(self.job.last_build.base_url,
                         'http+mock://jenkins.test/job/test-job/lastBuild/')
        # After request data, we now make use of the job builds data.
        self.assertIn('lastCompletedBuild', self.job.data)
        self.assertEqual(self.job.last_completed_build.base_url,
                         'http+mock://jenkins.test/job/test-job/41/')
        self.assertEqual(self.job.last_completed_build,
                         Build(self.job, number=41))
        self.assertEqual(self.job.last_failed_build,
                         Build(self.job, number=40))
        self.assertFalse(self.job.last_stable_build.exists)
        self.assertEqual(self.job.last_successful_build,
                         Build(self.job, number=32))
        # Can compare to other builds with data as well.
        self.assertEqual(self.job.last_unstable_build,
                         self.job.last_completed_build)
        # Missing data still leads to a symbolic reference.
        self.assertEqual(self.job.last_unsuccessful_build.base_url,
                         'http+mock://jenkins.test/job/test-job/lastUnsuccessfulBuild/')

        self.assertEqual(self.job.next_build_number, 43)

    def test_get_build(self) -> None:
        """
        Test retrieving a build based on its number.
        """

        self.assertEqual(self.job.get_build(3).number, 3)

        data = {
            'builds': [
                {'number': 1},
                {'number': 2}
            ]
        }
        self.adapter.register_uri('GET', '/job/test-job/api/json', json=data)
        self.assertIn('builds', self.job.data)
        self.assertFalse(self.job.get_build(3).exists)
        self.assertTrue(self.job.get_build(2).exists)

    def test_default_parameters(self) -> None:
        """
        Test retrieving parameters defined for a parameterized job.
        """

        data = {
            'actions': [],
            'property': [
                {},
                {
                    'parameterDefinitions': [
                        {
                            'name': 'VARIABLE_NAME',
                            'defaultParameterValue': {
                                'value': 'test'
                            }
                        },
                        {
                            'name': 'TEST_ENVIRONMENT',
                            'defaultParameterValue': {
                                'value': True
                            }
                        }
                    ]
                }
            ]
        }
        self.adapter.register_uri('GET', '/job/test-job/api/json', json=data)

        self.assertEqual(self.job.default_parameters, [
            {
                'name': 'VARIABLE_NAME',
                'value': 'test'
            },
            {
                'name': 'TEST_ENVIRONMENT',
                'value': 'True'
            }
        ])

        self.adapter.register_uri('GET', '/job/no-params/api/json', json={})
        self.assertEqual(Job(self.jenkins, name='no-params').default_parameters,
                         [])

    def test_build(self) -> None:
        """
        Test building the job.
        """


        matcher = self.adapter.register_uri('POST', '/job/test-job/build')
        self.job.build()
        self.assertTrue(matcher.called_once)

        # Test building with parameters
        # Missing type hint for requests_mock._Matcher.reset
        self.adapter.reset()
        self.job.build(parameters=[
            {
                'name': 'VARIABLE_NAME',
                'value': 'test'
            },
            {
                'name': 'TEST_ENVIRONMENT',
                'value': 'true'
            }
        ], token='my-token')
        self.assertTrue(matcher.called_once)

        # Dictionary based build with parameters
        params = self.adapter.register_uri('POST',
                                           '/job/test-job/buildWithParameters')
        self.job.build(parameters={'VARIABLE_NAME': 'jobtest',
                                   'TEST_ENVIRONMENT': 'true'})
        self.assertTrue(params.called_once)

    def test_comparison(self) -> None:
        """
        Test comparison method of the job.
        """

        self.assertTrue(self.job == Job(Jenkins('http+mock://jenkins.test/'),
                                        name='test-job'))
        self.assertFalse(self.job == Job(Jenkins('http://other.test/'),
                                         name='test-job'))
        self.assertFalse(self.job == Job(self.jenkins, name='other-job'))
        self.assertFalse(self.job == 'http+mock://jenkins.test/job/test-job/')

        child = Job(self.job, name='test-branch')
        self.assertFalse(child == self.job)
        self.assertFalse(child == Job(self.jenkins, name='test-branch'))
        self.assertEqual(hash(self.job),
                         hash('http+mock://jenkins.test/job/test-job/'))

class BuildTest(unittest.TestCase):
    """
    Test for build of a job on a Jenkins instance.
    """

    def setUp(self) -> None:
        self.jenkins, self.adapter = _setup_jenkins()
        self.job = Job(self.jenkins, name='test-job')
        self.build = Build(self.job, number=1)

    def test_properties(self) -> None:
        """
        Test retrieving properties for the build.
        """

        self.assertEqual(self.build.job, self.job)
        self.assertEqual(self.build.number, 1)
        build = Build(self.job,
                      url='http+mock://jenkins.test/job/test-job/lastBuild')
        self.adapter.register_uri('GET', '/job/test-job/lastBuild/api/json',
                                  json={
                                      'number': 2,
                                      'result': 'UNSTABLE',
                                      'building': True
                                  })
        self.assertEqual(build.number, 2)
        self.assertEqual(build.result, 'UNSTABLE')
        self.assertTrue(build.building)

        self.adapter.register_uri('GET',
                                  '/job/test-job/lastStableBuild/api/json',
                                  status_code=404)
        future = Build(self.job,
                       url='http+mock://jenkins.test/job/test-job/lastStableBuild')
        self.assertEqual(future.number, 0)

    def test_comparison(self) -> None:
        """
        Test comparison methods of the build.
        """

        other = Build(Job(self.jenkins, name='other'), number=1)

        self.assertTrue(self.build == Build(self.job, number=1))
        self.assertFalse(self.build == Build(self.job, number=2))
        self.assertFalse(self.build == other)
        self.assertFalse(self.build == 'http+mock://jenkins.test/job/test-job/1/')

        self.assertTrue(self.build < Build(self.job, number=2))
        self.assertFalse(self.build < Build(self.job, number=0))
        with self.assertRaises(TypeError):
            self.assertFalse(self.build < other)

        self.assertTrue(self.build > Build(self.job, number=0))
        self.assertFalse(self.build > Build(self.job, number=2))
        with self.assertRaises(TypeError):
            self.assertFalse(self.build > other)

        self.assertTrue(self.build <= Build(self.job, number=2))
        self.assertFalse(self.build <= Build(self.job, number=0))
        with self.assertRaises(TypeError):
            self.assertFalse(self.build <= other)

        self.assertTrue(self.build >= Build(self.job, number=1))
        self.assertFalse(self.build >= Build(self.job, number=2))
        with self.assertRaises(TypeError):
            self.assertFalse(self.build >= other)

        self.assertEqual(hash(self.build), hash((self.job, 1)))
        self.assertEqual(repr(self.build),
                         "Build('http+mock://jenkins.test/job/test-job/1/')")

        build = Build(self.job,
                      url='http+mock://jenkins.test/job/test-job/lastBuild')
        self.adapter.register_uri('GET', '/job/test-job/lastBuild/api/json',
                                  json={'number': 2})
        self.assertEqual(hash(build), hash((self.job, 2)))
        self.assertEqual(repr(build),
                         "Build(Job('http+mock://jenkins.test/job/test-job/'), number=2)")
