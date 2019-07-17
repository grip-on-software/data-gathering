# Stubs for hqlib.metric_source.test_report.junit_test_report (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...typing import DateTime
from ..abstract import test_report
from ..url_opener import UrlOpener
from typing import Any, List

class JunitTestReport(test_report.TestReport):
    metric_source_name: str = ...
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def metric_source_urls(self, *report_urls: str) -> List[str]: ...
