# Stubs for hqlib.metric.product.size_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerIsBetterMetric, Product
from ..metric_source_mixin import SonarDashboardMetric, SonarMetric
from hqlib.typing import MetricValue
from typing import List

class ProductLOC(SonarDashboardMetric, LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    def value(self) -> MetricValue: ...

class TotalLOC(SonarMetric, LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    def value(self) -> MetricValue: ...
    def recent_history(self) -> List[int]: ...
