# Stubs for hqlib.domain.measurement.metric (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..software_development.project import Project
from .metric_source import MetricSource
from .target import AdaptedTarget
from hqlib.typing import DateTime, MetricParameters, MetricValue, Number
from typing import Any, Dict, List, Optional, Tuple, Type

class ExtraInfo:
    headers: Any = ...
    title: Any = ...
    data: Any = ...
    def __init__(self, **kwargs: Any) -> None: ...
    def __add__(self, *args: Any): ...

class Metric:
    name: str = ...
    template: str = ...
    norm_template: str = ...
    unit: str = ...
    target_value: MetricValue = ...
    low_target_value: MetricValue = ...
    perfect_value: MetricValue = ...
    missing_template: str = ...
    missing_source_template: str = ...
    missing_source_id_template: str = ...
    perfect_template: str = ...
    url_label_text: str = ...
    comment_url_label_text: str = ...
    metric_source_class: Type[MetricSource] = ...
    extra_info_headers: Dict[str, str] = ...
    _subject: Any = ...
    _project: Optional[Project] = ...
    _metric_source: Optional[MetricSource] = ...
    def __init__(self, subject: Any=..., project: Optional[Project] = None) -> None: ...
    def format_text_with_links(self, text: str) -> str: ...
    @staticmethod
    def format_comment_with_links(text: str, url_dict: Dict[str, str], url_label: str) -> str: ...
    @classmethod
    def norm_template_default_values(cls: Any) -> MetricParameters: ...
    def is_applicable(self) -> bool: ...
    def normalized_stable_id(self): ...
    def stable_id(self) -> str: ...
    def set_id_string(self, id_string: str) -> None: ...
    def id_string(self) -> str: ...
    def target(self) -> MetricValue: ...
    def low_target(self) -> MetricValue: ...
    status: Any = ...
    def status_start_date(self) -> DateTime: ...
    def value(self) -> MetricValue: ...
    def report(self, max_subject_length: int=...) -> str: ...
    def norm(self) -> str: ...
    def url(self) -> Dict[str, str]: ...
    def comment(self) -> str: ...
    def comment_urls(self) -> Dict[str, str]: ...
    def recent_history(self) -> List[int]: ...
    def long_history(self) -> List[int]: ...
    def get_recent_history_dates(self) -> str: ...
    def get_long_history_dates(self) -> str: ...
    def y_axis_range(self) -> Tuple[int, int]: ...
    def numerical_value(self) -> Number: ...
    def extra_info(self) -> Optional[ExtraInfo]: ...
    def extra_info_rows(self) -> List: ...
    @staticmethod
    def convert_item_to_extra_info(item: Any): ...
