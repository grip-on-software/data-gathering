# Stubs for hqlib.metric_source.performance_report.spirit_splunk_csv (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..abstract import performance_report
from hqlib.metric_source import url_opener
from typing import Any, Iterable

class SpiritSplunkCSVPerformanceReport(performance_report.PerformanceReport, url_opener.UrlOpener):
    PRODUCT_COLUMN: int = ...
    PASS_FAIL_COLUMN: int = ...
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def fault_percentage(self, product: str) -> int: ...
    def urls(self, product: str) -> Iterable[str]: ...

class SpiritSplunkCSVPerformanceLoadTestReport(SpiritSplunkCSVPerformanceReport):
    metric_source_name: str = ...

class SpiritSplunkCSVPerformanceEnduranceTestReport(SpiritSplunkCSVPerformanceReport):
    metric_source_name: str = ...

class SpiritSplunkCSVPerformanceScalabilityTestReport(SpiritSplunkCSVPerformanceReport):
    metric_source_name: str = ...
