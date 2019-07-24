# Stubs for hqlib.metric.product.checkmarx_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .alerts_metrics import AlertsMetric
from typing import Any, List

class CheckmarxAlertsMetric(AlertsMetric):
    unit: str = ...
    norm_template: str = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    def extra_info_rows(self) -> List: ...

class HighRiskCheckmarxAlertsMetric(CheckmarxAlertsMetric):
    name: str = ...
    url_label_text: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...

class MediumRiskCheckmarxAlertsMetric(CheckmarxAlertsMetric):
    name: str = ...
    url_label_text: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...