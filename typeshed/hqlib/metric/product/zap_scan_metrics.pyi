# Stubs for hqlib.metric.product.zap_scan_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .alerts_metrics import AlertsMetric
from typing import Any

class ZAPScanAlertsMetric(AlertsMetric):
    unit: str = ...
    norm_template: str = ...
    metric_source_class: Any = ...
    extra_info_headers: Any = ...
    def extra_info_rows(self) -> list: ...

class HighRiskZAPScanAlertsMetric(ZAPScanAlertsMetric):
    name: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...
    url_label_text: str = ...

class MediumRiskZAPScanAlertsMetric(ZAPScanAlertsMetric):
    name: str = ...
    risk_level: str = ...
    risk_level_key: str = ...
    low_target_value: int = ...
    url_label_text: str = ...