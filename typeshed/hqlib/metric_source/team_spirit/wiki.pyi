# Stubs for hqlib.metric_source.team_spirit.wiki (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from hqlib.metric_source import beautifulsoup
from hqlib.metric_source.abstract import team_spirit
from hqlib.typing import DateTime
from typing import List

class Wiki(team_spirit.TeamSpirit, beautifulsoup.BeautifulSoupOpener):
    metric_source_name: str = ...
    def __init__(self, wiki_url: str) -> None: ...
    def metric_source_urls(self, *metric_source_ids: str) -> List[str]: ...
    def team_spirit(self, team_id: str) -> str: ...
    def datetime(self, *team_ids: str) -> DateTime: ...
