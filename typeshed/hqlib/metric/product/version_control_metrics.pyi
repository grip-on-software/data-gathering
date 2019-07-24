# Stubs for hqlib.metric.product.version_control_metrics (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import ExtraInfo, LowerIsBetterMetric
from ...metric_source import Branch, VersionControlSystem
from typing import Any, Dict

class UnmergedBranches(LowerIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    perfect_template: str = ...
    template: str = ...
    url_label_text: str = ...
    comment_url_label_text: str = ...
    target_value: int = ...
    low_target_value: int = ...
    metric_source_class: Any = ...
    def value(self): ...
    def comment_urls(self) -> Dict[str, str]: ...
    def comment(self) -> str: ...
    def extra_info(self) -> ExtraInfo: ...
    def format_text_with_links(self, text: str) -> str: ...
    @staticmethod
    def format_comment_with_links(text: str, url_dict: Dict[str, str], url_label: str) -> str: ...