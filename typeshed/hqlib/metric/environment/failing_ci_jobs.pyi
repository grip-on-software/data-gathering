# Stubs for hqlib.metric.environment.failing_ci_jobs (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from . import CIJobs
from typing import Any, List, Tuple

class FailingCIJobs(CIJobs):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    url_label_text: str = ...
    target_value: int = ...
    low_target_value: int = ...
    extra_info_headers: Any = ...
    def value(self): ...
    def extra_info_rows(self) -> List[Tuple[str, str, str]]: ...
