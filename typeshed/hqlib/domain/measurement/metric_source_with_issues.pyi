# Stubs for hqlib.domain.measurement.metric_source_with_issues (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .. import MetricSource
from typing import Any, Iterable, List

class MetricSourceWithIssues(MetricSource):
    class Issue:
        title: Any = ...
        def __init__(self, title: str) -> None: ...
    def __init__(self, *args: str, **kwargs: str) -> None: ...
    def obtain_issues(self, metric_source_ids: Iterable[str], priority: str) -> Any: ...
    def issues(self) -> List: ...
