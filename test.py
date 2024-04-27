"""
Runner for the data gathering module unit tests.

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


import os
from pathlib import Path
import sys
import unittest
import requests_mock
import xmlrunner
from gatherer.log import Log_Setup

def run_tests() -> int:
    """
    Run unit tests and write XML reports.
    """

    os.environ['GATHERER_SETTINGS_FILE'] = 'settings.cfg.example'
    os.environ['GATHERER_CREDENTIALS_FILE'] = 'credentials.cfg.example'

    requests_mock.mock.case_sensitive = True

    Log_Setup.init_logging('CRITICAL')

    loader = unittest.TestLoader()
    tests = loader.discover('test', pattern='*.py',
                            top_level_dir=Path(__file__).parent)
    runner = xmlrunner.XMLTestRunner(output='test-reports')
    result = runner.run(tests)
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_tests())
