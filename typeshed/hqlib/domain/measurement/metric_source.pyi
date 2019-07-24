# Stubs for hqlib.domain.measurement.metric_source (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..base import DomainObject
from hqlib.typing import DateTime
from typing import List

class MetricSource(DomainObject):
    metric_source_name: str = ...
    needs_values_as_list: bool = ...
    def __init__(self, *args: str, **kwargs: str) -> None: ...
    def metric_source_urls(self, *metric_source_ids: str) -> List[str]: ...
    def datetime(self, *metric_source_ids: str) -> DateTime: ...