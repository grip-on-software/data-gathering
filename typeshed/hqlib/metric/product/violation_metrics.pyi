# Stubs for hqlib.metric.product.violation_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerIsBetterMetric
from ...metric_source import OJAuditReport
from ..metric_source_mixin import SonarDashboardMetric, SonarMetric
from hqlib.typing import MetricValue
from typing import Any, List

class Violations(SonarDashboardMetric, LowerIsBetterMetric):
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    violation_type: str = ...
    extra_info_headers: Any = ...
    def extra_info_rows(self) -> List: ...
    @classmethod
    def norm_template_default_values(cls): ...
    def value(self) -> MetricValue: ...

class BlockerViolations(Violations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...
    url_label_text: str = ...

class CriticalViolations(Violations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...
    url_label_text: str = ...

class MajorViolations(Violations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...
    url_label_text: str = ...

class ViolationSuppressions(SonarMetric, LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    extra_info_headers: Any = ...
    def value(self) -> MetricValue: ...
    def extra_info_rows(self) -> List: ...

class OJAuditViolations(LowerIsBetterMetric):
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    violation_type: str = ...
    metric_source_class: Any = ...
    @classmethod
    def norm_template_default_values(cls): ...
    def value(self) -> MetricValue: ...

class OJAuditWarnings(OJAuditViolations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...

class OJAuditErrors(OJAuditViolations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...

class OJAuditExceptions(OJAuditViolations):
    name: str = ...
    violation_type: str = ...
    target_value: int = ...
    low_target_value: int = ...