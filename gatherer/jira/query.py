"""
Module that handles the JIRA API query.
"""

from datetime import datetime
from jira import JIRA
from ..utils import Iterator_Limiter

class Query(object):
    """
    Object that handles the JIRA API query using limiting.
    """

    def __init__(self, jira, username, password, options):
        self._jira = jira
        self._api = JIRA(options, basic_auth=(username, password))

        query = 'project={} AND updated > "{}"'
        self._query = query.format(self._jira.project_key,
                                   self._jira.updated_since.timestamp)
        self._search_fields = self._jira.search_fields
        self._latest_update = str(0)

        self._iterator_limiter = Iterator_Limiter(size=100, maximum=100000)

    def update(self):
        """
        Update the internal iteration tracker after processing a query.
        """

        self._iterator_limiter.update()

    def perform_batched_query(self, had_issues):
        """
        Retrieve a batch of issue results from the JIRA API.
        """

        if not self._iterator_limiter.check(had_issues):
            return []

        self._latest_update = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M")
        return self._api.search_issues(self._query,
                                       startAt=self._iterator_limiter.skip,
                                       maxResults=self._iterator_limiter.size,
                                       expand='attachment,changelog',
                                       fields=self._search_fields)

    @property
    def latest_update(self):
        """
        Retrieve the latest time that the query retrieved data.
        """

        return self._latest_update