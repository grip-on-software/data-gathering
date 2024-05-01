"""
Tests for module for initializing logging.

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

from argparse import ArgumentParser
import logging
import unittest
from unittest.mock import patch, MagicMock
from gatherer.log import Log_Setup

class LogSetupTest(unittest.TestCase):
    """
    Tests for utility class that initializes and registers logging options.
    """

    def test_is_ignored(self) -> None:
        """
        Test checking whether a log message is ignored in certain contexts.
        """

        ignored = [
            'Could not load sprint data, no sprint matching possible.',
            "Controller status: Some parts are not OK: Status 'tracker': "
                'Next scheduled gather moment is in 12:00',
            'No BigBoat host defined for TEST',
            'Cannot retrieve repository source for dummy repository on git.test'
        ]
        relevant = [
            'Cannot initialize agent logging handler, incompatible HTTPHandler',
            'Could not set up TFS API',
            'Invalid JSON response from controller API: foobar'
        ]

        for message in ignored:
            self.assertTrue(Log_Setup.is_ignored(message))
        for message in relevant:
            self.assertFalse(Log_Setup.is_ignored(message))

    def test_add_argument(self) -> None:
        """
        Test registering a log level argument in an argument parser.
        """

        parser = ArgumentParser()
        Log_Setup.add_argument(parser)
        self.assertEqual(parser.parse_args([]).log, 'WARNING')
        self.assertEqual(parser.parse_args(['--log', 'INFO']).log, 'INFO')

    def test_add_upload_arguments(self) -> None:
        """
        Test adding additional arguments to configure transfer of logging data.
        """

        parser = ArgumentParser()
        Log_Setup.add_upload_arguments(parser)
        with patch('sys.stderr', autospec=True):
            with self.assertRaises(SystemExit):
                self.assertFalse(parser.parse_args(['--no-ssh']).ssh)

        with patch.dict('os.environ', {'AGENT_LOGGING': 'true'}):
            Log_Setup.add_upload_arguments(parser)
            args = parser.parse_args([])
            self.assertEqual(args.ssh, '$SSH_HOST')
            self.assertEqual(args.cert, '$SSH_HTTPS_CERT')

            populated = ArgumentParser()
            populated.add_argument('--ssh', help='My own argument')
            Log_Setup.add_upload_arguments(populated)
            population = populated.parse_args(['--ssh', 'ssh.test'])
            self.assertEqual(population.ssh, 'ssh.test')
            self.assertFalse(hasattr(population, 'cert'))

    @patch('gatherer.log.Log_Setup.init_logging', autospec=True)
    @patch('gatherer.log.Log_Setup.add_agent_handler', autospec=True)
    def test_parse_args(self, add: MagicMock, init: MagicMock) -> None:
        """
        Test configuring log packet uploading.
        """

        parser = ArgumentParser()
        Log_Setup.add_argument(parser)
        Log_Setup.parse_args(parser.parse_args([]))
        init.assert_called_once_with('WARNING')
        add.assert_not_called()

        with patch.dict('os.environ', {'AGENT_LOGGING': 'true'}):
            Log_Setup.add_upload_arguments(parser)
            parser.add_argument('--project', default='TEST')
            Log_Setup.parse_args(parser.parse_args([]))
            add.assert_called_once_with('$SSH_HOST', '$SSH_HTTPS_CERT', 'TEST')

    @patch('gatherer.log.HTTPHandler', autospec=True)
    @patch('ssl.create_default_context', autospec=True)
    @patch('logging.getLogger', autospec=True)
    def test_add_agent_handler(self, logger: MagicMock, ssl_context: MagicMock,
                               handler: MagicMock) -> None:
        """
        Test create a HTTPS-based logging handler.
        """

        Log_Setup.add_agent_handler('controller.test', 'test/sample/cert',
                                    'TEST')
        ssl_context.assert_called_once_with(cafile='test/sample/cert')
        handler.assert_called_once_with('controller.test',
                                        'https://controller.test/auth/log.py?project=TEST',
                                        method='POST', secure=True,
                                        context=ssl_context.return_value)
        handler.return_value.setLevel.assert_called_once_with(logging.WARNING)

        logger.return_value.addHandler.assert_called_once_with(handler.return_value)

        logger.reset_mock()
        handler.side_effect = TypeError
        Log_Setup.add_agent_handler('-', 'test/sample/cert', 'TEST')
        logger.return_value.addHandler.assert_not_called()
