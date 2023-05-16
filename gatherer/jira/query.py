"""
Module that handles the JIRA API query.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from datetime import datetime
import logging
from typing import Iterable, Optional, TYPE_CHECKING
from jira import Issue, JIRA
from ..domain import source
from ..utils import format_date, Iterator_Limiter
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira
else:
    Jira = object

class Query:
    """
    Object that handles the JIRA API query using limiting.
    """

    DATE_FORMAT = '%Y-%m-%d %H:%M'
    QUERY_FORMAT = 'project={0} AND updated > "{1}"'


    def __init__(self, jira: Jira, jira_source: source.Jira,
                 query: Optional[str] = None) -> None:
        self._jira = jira
        self._api = jira_source.jira_api

        updated_since = format_date(self._jira.updated_since.date,
                                    date_format=self.DATE_FORMAT)
        if query is not None:
            query = f"{self.QUERY_FORMAT} AND ({query})"
        else:
            query = self.QUERY_FORMAT
        self._query = query.format(self._jira.project_key, updated_since)
        logging.info('Using query %s', self._query)

        self._search_fields = self._jira.search_fields
        self._latest_update = str(0)

        self._iterator_limiter = Iterator_Limiter(size=100, maximum=100000)

    def update(self) -> None:
        """
        Update the internal iteration tracker after processing a query.
        """

        self._iterator_limiter.update()

    def perform_batched_query(self, had_issues: bool) -> Iterable[Issue]:
        """
        Retrieve a batch of issue results from the JIRA API.
        """

        if not self._iterator_limiter.check(had_issues):
            return []

        self._latest_update = format_date(datetime.now(),
                                          date_format=self.DATE_FORMAT)
        return self._api.search_issues(self._query,
                                       startAt=self._iterator_limiter.skip,
                                       maxResults=self._iterator_limiter.size,
                                       expand='attachment,changelog',
                                       fields=self._search_fields)

    @property
    def api(self) -> JIRA:
        """
        Retrieve the Jira API connection.
        """

        return self._api

    @property
    def latest_update(self) -> str:
        """
        Retrieve the latest time that the query retrieved data.
        """

        return self._latest_update
