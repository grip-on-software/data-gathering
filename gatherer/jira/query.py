"""
Module that handles the JIRA API query.
"""

import logging
from builtins import str, object
from datetime import datetime
from jira import JIRA
from ..utils import format_date, Iterator_Limiter

class Query(object):
    """
    Object that handles the JIRA API query using limiting.
    """

    DATE_FORMAT = '%Y-%m-%d %H:%M'
    QUERY = 'project={0} AND updated > "{1}"'


    def __init__(self, jira, auth, options, query=None):
        self._jira = jira
        self._api = JIRA(options, basic_auth=auth)

        updated_since = format_date(self._jira.updated_since.date,
                                    date_format=self.DATE_FORMAT)
        if query is not None:
            query = "{0} AND ({1})".format(self.QUERY, query)
        else:
            query = self.QUERY
        self._query = query.format(self._jira.project_key, updated_since)
        logging.info('Using query %s', self._query)

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

        self._latest_update = format_date(datetime.now(),
                                          date_format=self.DATE_FORMAT)
        return self._api.search_issues(self._query,
                                       startAt=self._iterator_limiter.skip,
                                       maxResults=self._iterator_limiter.size,
                                       expand='attachment,changelog',
                                       fields=self._search_fields)

    @property
    def api(self):
        """
        Retrieve the Jira API connection.
        """

        return self._api

    @property
    def latest_update(self):
        """
        Retrieve the latest time that the query retrieved data.
        """

        return self._latest_update
