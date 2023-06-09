# Stubs for hqlib.metric_source.abstract.issue_log (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ... import domain
from typing import List, Tuple

class IssueLog(domain.MetricSource):
    metric_source_name: str = ...
    def ignored_lists(self) -> List[str]: ...

class RiskLog(IssueLog):
    metric_source_name: str = ...
    def ignored_lists(self) -> List[str]: ...

class ActionLog(IssueLog):
    metric_source_name: str = ...
    def ignored_lists(self) -> List[str]: ...
    def nr_of_over_due_actions(self, *metric_source_ids: str) -> int: ...
    def over_due_actions_url(self, *metric_source_ids: str) -> List[Tuple[str, str, str]]: ...
    def nr_of_inactive_actions(self, *metric_source_ids: str) -> int: ...
    def inactive_actions_url(self, *metric_source_ids: str) -> List[Tuple[str, str, str]]: ...
