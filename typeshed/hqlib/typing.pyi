# Stubs for hqlib.typing (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import datetime
from .domain.base import DomainObject
from distutils.version import LooseVersion
from typing import Dict, Optional, Sequence, Tuple, Union

Number = Union[float, int]
DateTime = datetime.datetime
TimeDelta = datetime.timedelta
MetricValue = Union[Number, str, LooseVersion]
MetricParameters = Dict[str, MetricValue]
DashboardColumns = Sequence[Tuple[str, int]]
DashboardRows = Sequence[Sequence[Tuple[Union[DomainObject, str], str, Optional[Tuple[int, int]]]]]
Dashboard = Tuple[DashboardColumns, DashboardRows]