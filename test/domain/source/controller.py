"""
Tests for agent controller source domain object.

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
import requests_mock
from gatherer.domain.project import Project
from gatherer.domain.source import Source

class ControllerTest(unittest.TestCase):
    """
    Tests for agent controller source.
    """

    def setUp(self) -> None:
        self.prefix = 'https://controller.test/auth'
        self.source = Source.from_type('controller', name='test-controller',
                                       url=f'{self.prefix}/')

    def test_environment(self) -> None:
        """
        Test retrieving an indicator of the environment of the source.
        """

        self.assertEqual(self.source.environment, self.prefix)

    @requests_mock.Mocker()
    @patch('gatherer.domain.source.controller.json', autospec=True)
    @patch('gatherer.domain.source.controller.Path', autospec=True)
    def test_update_identity(self, request: requests_mock.Mocker,
                             path: MagicMock, json: MagicMock) -> None:
        """
        Test updating the source to accept a public key as an identity.
        """

        project = Project('TEST')
        url = f'{self.prefix}/agent.py?project=TEST&agent=$JIRA_KEY'
        secrets = {"salts": {"salt": "foo", "pepper": "bar"}}
        request.post(url, json=secrets)
        public_key = 'my-public-key'

        self.source.update_identity(project, public_key, dry_run=True)
        self.assertFalse(request.called)
        self.source.update_identity(project, public_key)
        self.assertTrue(request.called)
        path.assert_called_once_with('secrets.json')
        json.dump.assert_called_once()
        self.assertEqual(json.dump.call_args.args[0], secrets)

        request.post(url, status_code=403, text='error')
        with self.assertRaises(RuntimeError):
            self.source.update_identity(project, public_key)

        path.reset_mock()
        json.reset_mock()
        request.post(url, text='not json')
        self.source.update_identity(project, public_key)
        path.return_value.assert_not_called()
        json.dump.assert_not_called()
