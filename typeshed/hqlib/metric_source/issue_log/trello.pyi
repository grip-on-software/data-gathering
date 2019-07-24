# Stubs for hqlib.metric_source.issue_log.trello (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...metric_source import url_opener
from ...typing import DateTime, TimeDelta
from hqlib.metric_source.abstract.issue_log import ActionLog
from typing import Any, List, Tuple

class TrelloBoard(ActionLog):
    metric_source_name: str = ...
    board_data_url: str = ...
    def __init__(self, appkey: str, token: str, *args: Any, **kwargs: Any) -> None: ...
    def ignored_lists(self) -> List[str]: ...
    def datetime(self, *metric_source_ids: str) -> DateTime: ...
    def nr_of_over_due_cards(self, *board_ids: str) -> int: ...
    def nr_of_inactive_cards(self, *board_ids: str, days: int=...) -> int: ...
    def over_due_cards_url(self, *board_ids: str) -> List[Tuple[str, str, str]]: ...
    def inactive_cards_url(self, *board_ids: str, days: int=...) -> List[Tuple[str, str, str]]: ...
    def url(self, object_id: str=...) -> str: ...
    def metric_source_urls(self, *metric_source_ids: str) -> List[str]: ...
    def nr_of_over_due_actions(self, *metric_source_ids: str) -> int: ...
    def over_due_actions_url(self, *metric_source_ids: str) -> List[Tuple[str, str, str]]: ...
    def nr_of_inactive_actions(self, *metric_source_ids: str) -> int: ...
    def inactive_actions_url(self, *metric_source_ids: str) -> List[Tuple[str, str, str]]: ...