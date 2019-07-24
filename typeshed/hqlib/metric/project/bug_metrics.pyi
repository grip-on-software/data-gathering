# Stubs for hqlib.metric.project.bug_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import LowerIsBetterMetric
from typing import Any

class OpenBugs(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    template: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    url_label_text: str = ...
    def value(self): ...

class OpenSecurityBugs(OpenBugs):
    name: str = ...
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...

class OpenStaticSecurityAnalysisBugs(OpenSecurityBugs):
    name: str = ...
    unit: str = ...
    metric_source_class: Any = ...

class OpenFindings(OpenBugs):
    name: str = ...
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...

class TechnicalDebtIssues(OpenBugs):
    name: str = ...
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...

class QualityGate(OpenBugs):
    name: str = ...
    unit: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...