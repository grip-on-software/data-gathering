# Stubs for hqlib.metric.product.performance.performance_test_age (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .base_performance_metric import PerformanceMetricMixin
from hqlib import domain
from typing import Any

class PerformanceLoadTestAge(PerformanceMetricMixin, domain.MetricSourceAgeMetric):
    target_value: int = ...
    low_target_value: int = ...
    name: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    metric_source_class: Any = ...

class PerformanceEnduranceTestAge(PerformanceMetricMixin, domain.MetricSourceAgeMetric):
    target_value: int = ...
    low_target_value: int = ...
    name: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    metric_source_class: Any = ...

class PerformanceScalabilityTestAge(PerformanceMetricMixin, domain.MetricSourceAgeMetric):
    target_value: int = ...
    low_target_value: int = ...
    name: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    metric_source_class: Any = ...