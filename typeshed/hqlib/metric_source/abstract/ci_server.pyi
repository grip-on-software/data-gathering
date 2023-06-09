# Stubs for hqlib.metric_source.abstract.ci_server (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ... import domain
from typing import Dict, List, Optional, Tuple

class CIServer(domain.MetricSource):
    metric_source_name: str = ...
    def number_of_active_jobs(self) -> int: ...
    def number_of_failing_jobs(self) -> int: ...
    def number_of_unused_jobs(self) -> int: ...
    def failing_jobs_url(self) -> Optional[List[Tuple[str, str, str]]]: ...
    def unused_jobs_url(self) -> Optional[List[Tuple[str, str, str]]]: ...
