# Stubs for hqlib.metric.product.logical_test_case_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerIsBetterMetric
from ...metric_source.abstract.backlog import Backlog
from hqlib.typing import MetricValue
from typing import Any

class LogicalTestCaseMetric(LowerIsBetterMetric):
    unit: str = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    def value(self): ...

class LogicalTestCasesNotReviewed(LogicalTestCaseMetric):
    name: str = ...
    unit: Any = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...

class LogicalTestCasesNotApproved(LogicalTestCaseMetric):
    name: str = ...
    unit: Any = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...

class LogicalTestCasesNotAutomated(LogicalTestCaseMetric):
    name: str = ...
    unit: Any = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...

class ManualLogicalTestCases(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    never_template: str = ...
    no_manual_tests_template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    def value(self): ...

class NumberOfManualLogicalTestCases(LogicalTestCaseMetric):
    name: str = ...
    unit: Any = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...

class DurationOfManualLogicalTestCases(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    url_label_text: str = ...
    def value(self) -> MetricValue: ...

class ManualLogicalTestCasesWithoutDuration(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    url_label_text: str = ...
    def value(self): ...
