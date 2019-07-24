# Stubs for hqlib.metric_source.ojaudit (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .. import domain
from typing import Any, List

class OJAuditReport(domain.MetricSource):
    metric_source_name: str = ...
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def violations(self, violation_type: str, *metric_source_ids: Any) -> int: ...
    def metric_source_urls(self, *report_urls: str) -> List[str]: ...