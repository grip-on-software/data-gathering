# Stubs for hqlib.metric.product.openvas_scan_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .alerts_metrics import AlertsMetric
from typing import Any

class OpenVASScanAlertsMetric(AlertsMetric):
    unit: str = ...
    norm_template: str = ...
    metric_source_class: Any = ...

class HighRiskOpenVASScanAlertsMetric(OpenVASScanAlertsMetric):
    name: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...

class MediumRiskOpenVASScanAlertsMetric(OpenVASScanAlertsMetric):
    name: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...
