from typing import Any, Optional, Type, Union
from unittest import TestCase, TestResult, TestSuite, TextTestRunner

class XMLTestRunner(TextTestRunner):
    def __init__(self, output: str = '.', outsuffix: Optional[str] = None,
                 elapsed_times: bool =True, encoding: str = 'UTF-8',
                 resultclass: Optional[Type[TestResult]] = None,
                 **kwargs: Any) -> None: ...
    def run(self, test: Union[TestSuite, TestCase]) -> TestResult: ...
