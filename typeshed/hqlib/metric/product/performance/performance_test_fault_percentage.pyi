# Stubs for hqlib.metric.product.performance.performance_test_fault_percentage (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .base_performance_metric import PerformanceMetricMixin
from hqlib import domain
from hqlib.typing import MetricValue
from typing import Any, List

class PerformanceTestFaultPercentage(PerformanceMetricMixin, domain.LowerIsBetterMetric):
    target_value: int = ...
    low_target_value: int = ...
    unit: str = ...
    applicable_metric_source_classes: List[domain.MetricSource] = ...
    def is_applicable(self) -> bool: ...
    def value(self) -> MetricValue: ...

class PerformanceLoadTestFaultPercentage(PerformanceTestFaultPercentage):
    name: str = ...
    norm_template: str = ...
    template: str = ...
    metric_source_class: Any = ...
    applicable_metric_source_classes: Any = ...

class PerformanceEnduranceTestFaultPercentage(PerformanceTestFaultPercentage):
    name: str = ...
    norm_template: str = ...
    template: str = ...
    metric_source_class: Any = ...
    applicable_metric_source_classes: Any = ...

class PerformanceScalabilityTestFaultPercentage(PerformanceTestFaultPercentage):
    name: str = ...
    norm_template: str = ...
    template: str = ...
    metric_source_class: Any = ...
    applicable_metric_source_classes: Any = ...
