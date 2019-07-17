# Stubs for hqlib.metric.product.unittest_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from hqlib.domain import LowerIsBetterMetric
from typing import Any

class FailingUnittests(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    no_tests_template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    def value(self): ...
    def status(self) -> str: ...
