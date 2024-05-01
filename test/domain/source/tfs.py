"""
Tests for Team Foundation Server source domain object.

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

import unittest
from unittest.mock import patch, MagicMock
from gatherer.config import Configuration
from gatherer.domain.source import Source, TFS, TFVC
from gatherer.git.tfs import TFS_Project, TFVC_Project

class TFSTest(unittest.TestCase):
    """
    Tests for Team Foundation Server source repository using Git.
    """

    def setUp(self) -> None:
        Configuration.clear()
        self.source = Source.from_type('tfs', name='test-tfs',
                                       url='http://tfs.test/tfs/col/_git/repo/')

    def tearDown(self) -> None:
        Configuration.clear()

    def test_is_tfs_url(self) -> None:
        """
        Test checking whether a URL is part of a TFS instance.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('source.test')
        credentials.set('source.test', 'tfs', 'true')
        self.assertTrue(TFS.is_tfs_url('https://source.test/tfs/col/_git/repo'))

        credentials.add_section('archived.test')
        credentials.set('archived.test', 'host', 'source.test')
        self.assertTrue(TFS.is_tfs_url('https://archived.test/tfs/col/_git/a/'))
        self.assertFalse(TFS.is_tfs_url('https://archived.test/some/other/repo',
                                        follow_host_change=False))

    def test_url(self) -> None:
        """
        Test retrieving the final URL after applying credentials.
        """

        self.assertEqual(self.source.url, 'http://tfs.test/tfs/col/_git/repo')

        # HTTP to SSH conversion
        credentials = Configuration.get_credentials()
        credentials.add_section('env-tfs.test')
        credentials.set('env-tfs.test', 'env', 'CREDENTIALS_FILE')
        env = Source.from_type('tfs', name='env-tfs',
                               url='http://env-tfs.test/tfs/col/_git/BASE/Nest')
        self.assertEqual(env.url, 'env-tfs.test:tfs/col/_git/base/nest')

        # Username from credentials added
        credentials.set('env-tfs.test', 'username', 'user')
        env_user = Source.from_type('tfs', name='env-tfs-user',
                                    url='http://env-tfs.test/tfs/col/_git/repo')
        self.assertEqual(env_user.url, 'user@env-tfs.test:tfs/col/_git/repo')

    def test_properties(self) -> None:
        """
        Test retrieving most properties of the TFS source.
        """

        credentials = Configuration.get_credentials()
        credentials.add_section('prop-tfs.test')
        credentials.set('prop-tfs.test', 'protocol', 'http')
        credentials.set('prop-tfs.test', 'web_port', '8080')

        prop = Source.from_type('tfs', name='prop-tfs',
                                url='user@prop-tfs.test:tfs/nest/col/_git/repo')
        if not isinstance(prop, TFS): # pragma: no cover
            self.fail("Incorrect source")

        self.assertEqual(prop.environment, ('http://prop-tfs.test:8080',
                                            'tfs/nest', 'col'))
        self.assertEqual(prop.environment_url,
                         'http://prop-tfs.test:8080/tfs/nest/col')
        self.assertEqual(prop.web_url,
                         'http://prop-tfs.test:8080/tfs/nest/col/repo')
        self.assertEqual(prop.tfs_collections, ('tfs/nest', 'col'))
        self.assertEqual(prop.tfs_repo, 'repo')

        no_repo = Source.from_type('tfs', name='no-repo-tfs',
                                   url='no-repo-tfs.test:tfs/foo/bar')
        self.assertEqual(no_repo.web_url, 'http://no-repo-tfs.test/tfs/foo/bar')

    def test_tfs_api(self) -> None:
        """
        Test retrieving an instance of the TFS API connection.
        """

        if not isinstance(self.source, TFS): # pragma: no cover
            self.fail("Incorrect source")

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'http://tfs.test'}):
            with self.assertRaises(RuntimeError):
                self.assertIsNone(self.source.tfs_api)

        Configuration.clear()

        api = self.source.tfs_api
        self.assertIsInstance(api, TFS_Project)
        # Requesting the property again provides the same object.
        self.assertEqual(self.source.tfs_api, api)

    def test_check_credentials(self) -> None:
        """
        Test checking whether the source environment is within the credentials.
        """

        self.assertTrue(self.source.check_credentials_environment())

        credentials = Configuration.get_credentials()
        credentials.add_section('coll-tfs.test')
        credentials.set('coll-tfs.test', 'tfs', 'tfs/org')

        coll = Source.from_type('tfs', name='coll-tfs',
                                url='http://coll-tfs.test/tfs/org/_git/repo')
        self.assertTrue(coll.check_credentials_environment())
        out = Source.from_type('tfs', name='coll-tfs-out',
                                url='http://coll-tfs.test/tfs/other/_git/repo')
        self.assertFalse(out.check_credentials_environment())

    @patch('gatherer.domain.source.tfs.TFS_Project', autospec=True)
    def test_get_sources(self, api: MagicMock) -> None:
        """
        Test retrieving information about additional data sources.
        """

        api.side_effect = RuntimeError
        self.assertEqual(self.source.get_sources(), [])
        api.side_effect = None

        attrs = {'repositories.return_value': [
            {
                'remoteUrl': 'http://some-alias-to-tfs.test/tfs/col/_git/other',
                'name': 'other'
            }
        ]}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.get_sources(), [
            Source.from_type('tfs', name='other',
                             url='http://tfs.test/tfs/col/_git/other')
        ])

class TFVCTest(unittest.TestCase):
    """
    Tests for Team Foundation Server source repository using TFVC.
    """

    def setUp(self) -> None:
        self.source = Source.from_type('tfvc', name='test-tfvc',
                                       url='http://tfvc.test/tfs/foo/bar/baz/')

    def test_tfvc_project(self) -> None:
        """
        Test retrieveing the project name of the TFVC repository.
        """

        if not isinstance(self.source, TFVC): # pragma: no cover
            self.fail("Incorrect source")

        self.assertEqual(self.source.tfvc_project, 'bar')

    def test_environment_url(self) -> None:
        """
        Test retrieving a URL for the environment that the source lives in.
        """

        self.assertEqual(self.source.environment_url,
                         'http://tfvc.test/tfs/foo/bar')

        one = Source.from_type('tfvc', name='one-tfvc',
                               url='http://one.test/tfs')
        self.assertEqual(one.url, 'http://one.test/tfs')

    def test_tfs_api(self) -> None:
        """
        Test retrieving an instance of the TFVC API connection.
        """

        if not isinstance(self.source, TFVC): # pragma: no cover
            self.fail("Incorrect source")

        Configuration.clear()

        with patch.dict('os.environ',
                        {'GATHERER_URL_BLACKLIST': 'http://tfvc.test'}):
            with self.assertRaises(RuntimeError):
                self.assertIsNone(self.source.tfs_api)

        Configuration.clear()

        api = self.source.tfs_api
        self.assertIsInstance(api, TFVC_Project)
        # Requesting the property again provides the same object.
        self.assertEqual(self.source.tfs_api, api)

    @patch('gatherer.domain.source.tfs.TFVC_Project', autospec=True)
    def test_get_sources(self, api: MagicMock) -> None:
        """
        Test retrieving information about additional data sources.
        """

        api.side_effect = RuntimeError
        self.assertEqual(self.source.get_sources(), [])
        api.side_effect = None

        attrs = {'projects.return_value': [{
            'name': 'other'
        }]}
        api.return_value.configure_mock(**attrs)
        self.assertEqual(self.source.get_sources(), [
            Source.from_type('tfvc', name='other',
                             url='http://tfvc.test/tfs/foo/other')
        ])
