# Stubs for hqlib.metric.product.aggregated_test_coverage_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import HigherIsBetterMetric, MetricSourceAgeMetric
from typing import Any

class AggregatedTestCoverage(HigherIsBetterMetric):
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    perfect_value: int = ...
    metric_source_class: Any = ...
    covered_items: str = ...
    covered_item: str = ...
    @classmethod
    def norm_template_default_values(cls): ...
    def value(self): ...

class AggregatedTestStatementCoverage(AggregatedTestCoverage):
    name: str = ...
    target_value: int = ...
    low_target_value: int = ...
    covered_item: str = ...
    covered_items: str = ...

class AggregatedTestBranchCoverage(AggregatedTestCoverage):
    name: str = ...
    target_value: int = ...
    low_target_value: int = ...
    covered_item: str = ...
    covered_items: str = ...

class AggregatedTestCoverageReportAge(MetricSourceAgeMetric):
    name: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    metric_source_class: Any = ...
