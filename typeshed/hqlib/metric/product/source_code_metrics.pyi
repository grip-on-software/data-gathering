# Stubs for hqlib.metric.product.source_code_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerPercentageIsBetterMetric
from ..metric_source_mixin import SonarDashboardMetric, SonarViolationsMetric
from hqlib.typing import MetricParameters
from typing import Any

class CommentedLOC(SonarDashboardMetric, LowerPercentageIsBetterMetric):
    name: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...

class MethodQualityMetric(SonarViolationsMetric, LowerPercentageIsBetterMetric):
    norm_template: str = ...
    template: str = ...
    attribute: str = ...
    target_value: int = ...
    low_target_value: int = ...
    @classmethod
    def norm_template_default_values(cls: Any) -> MetricParameters: ...

class CyclomaticComplexity(MethodQualityMetric):
    name: str = ...
    attribute: str = ...

class LongMethods(MethodQualityMetric):
    name: str = ...
    attribute: str = ...

class ManyParameters(MethodQualityMetric):
    name: str = ...
    attribute: str = ...
