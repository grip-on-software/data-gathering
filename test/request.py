"""
Tests for module that provides HTTP request sessions.

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

from io import StringIO
from typing import Any, Dict
import unittest
from unittest.mock import patch, MagicMock
import requests
from requests.auth import HTTPBasicAuth
import requests_mock
from gatherer import __version__ as version
from gatherer.request import Session

class SessionTest(unittest.TestCase):
    """
    Tests for HTTP request session.
    """

    @requests_mock.Mocker()
    def test_is_code(self, request: requests_mock.Mocker) -> None:
        """
        Test checking whether the response has a status code consistent with
        a HTTP status name.
        """

        request.get('http://resp.test', status_code=404)
        response = requests.get('http://resp.test', timeout=3)
        self.assertTrue(Session.is_code(response, 'not_found'))

    @patch('gatherer.request.Path', autospec=True)
    def test_init(self, path: MagicMock) -> None:
        """
        Test creating a Session with headers and other options.
        """

        attrs: Dict[str, Any] = {'exists.return_value': False}
        path.return_value.configure_mock(**attrs)

        auth = HTTPBasicAuth('sessionuser', 'sessionpass')
        session = Session(verify=True, auth=auth)
        self.assertTrue(session.verify)
        self.assertEqual(session.auth, auth)
        user_agent = session.headers['User-Agent'] \
            if isinstance(session.headers['User-Agent'], str) \
            else str(session.headers['User-Agent'], encoding='utf-8')
        self.assertTrue(user_agent.endswith(f' gatherer/{version}'),
                        msg=f'User-Agent header missing module: {user_agent}')

        attrs = {
            'exists.return_value': True,
            'open.return_value': StringIO(f'{version}-tests-sha\n')
        }
        path.return_value.configure_mock(**attrs)
        session = Session()
        user_agent = session.headers['User-Agent'] \
            if isinstance(session.headers['User-Agent'], str) \
            else str(session.headers['User-Agent'], encoding='utf-8')
        self.assertTrue(user_agent.endswith(f' gatherer/{version}-tests-sha'),
                        msg=f'User-Agent header missing module: {user_agent}')
