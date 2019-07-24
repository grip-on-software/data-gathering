# Stubs for hqlib.domain.measurement.metric_source_age_metric (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from . import directed_metric
from hqlib.typing import MetricValue

class MetricSourceAgeMetric(directed_metric.LowerIsBetterMetric):
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    def value(self) -> MetricValue: ...