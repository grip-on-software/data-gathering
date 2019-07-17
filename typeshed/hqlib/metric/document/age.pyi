# Stubs for hqlib.metric.document.age (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerIsBetterMetric
from typing import Any

class DocumentAge(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    missing_template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    def value(self): ...
