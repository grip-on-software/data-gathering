# Stubs for hqlib.metric.meta_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..domain import HigherPercentageIsBetterMetric, LowerPercentageIsBetterMetric, PercentageMetric
from typing import Any, Tuple

class MetaMetric(PercentageMetric):
    metric_statuses: Tuple = ...
    status_text1: str = ...
    status_text2: str = ...
    status_color_text: str = ...
    target_prefix_text: str = ...
    low_target_prefix_text: str = ...
    norm_template: str = ...
    template: str = ...
    def value(self): ...

class GreenMetaMetric(MetaMetric, HigherPercentageIsBetterMetric):
    metric_statuses: Any = ...
    status_text1: str = ...
    status_text2: str = ...
    target_prefix_text: str = ...
    low_target_prefix_text: str = ...
    status_color_text: str = ...
    target_value: int = ...
    low_target_value: int = ...

class RedMetaMetric(MetaMetric, LowerPercentageIsBetterMetric):
    metric_statuses: Any = ...
    status_text1: str = ...
    status_text2: str = ...
    status_color_text: str = ...
    target_value: int = ...
    low_target_value: int = ...

class YellowMetaMetric(MetaMetric, LowerPercentageIsBetterMetric):
    metric_statuses: Any = ...
    status_text1: str = ...
    status_text2: str = ...
    status_color_text: str = ...
    target_value: int = ...
    low_target_value: int = ...

class GreyMetaMetric(MetaMetric, LowerPercentageIsBetterMetric):
    metric_statuses: Any = ...
    status_text1: str = ...
    status_text2: str = ...
    status_color_text: str = ...
    target_value: int = ...
    low_target_value: int = ...

class MissingMetaMetric(MetaMetric, LowerPercentageIsBetterMetric):
    metric_statuses: Any = ...
    status_text1: str = ...
    status_text2: str = ...
    status_color_text: str = ...
    target_value: int = ...
    low_target_value: int = ...
