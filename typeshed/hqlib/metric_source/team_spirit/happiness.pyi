# Stubs for hqlib.metric_source.team_spirit.happiness (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from hqlib.metric_source.abstract import team_spirit
from hqlib.typing import DateTime
from typing import Callable

class Happiness(team_spirit.TeamSpirit):
    metric_source_name: str = ...
    def __init__(self, url: str, url_read: Callable[[str], str]=...) -> None: ...
    def team_spirit(self, team_id: str) -> str: ...
    def datetime(self, *team_ids: str) -> DateTime: ...