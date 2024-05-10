"""
Data connection for the project definitions and metrics at a SonarQube server.

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
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, \
    TYPE_CHECKING
from urllib.parse import parse_qs, parse_qsl, urlsplit
from packaging.version import Version as PackageVersion
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from . import parser
from ..base import Data, DataUrl, Parser, MetricNames, Revision, Version
from ...request import Session
from ...utils import Iterator_Limiter, convert_local_datetime, format_date, \
    get_local_datetime
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ...domain import Project, Source
else:
    Project = object
    Source = object

class Sonar_Data(Data):
    """
    Project definition stored in a SonarQube server.
    """

    START_DATE = datetime(1970, 1, 1, 0, 0, 0)

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url)

        self._session = Session()
        self._session.verify = not source.get_option('unsafe_hosts')

        # For older versions of Sonar, in particular SonarCloud, we provide
        # the organization parameter for (additional) filtering
        if project.quality_metrics_name is not None and \
            PackageVersion('8.0') < PackageVersion(source.version) < PackageVersion('8.7'):
            self._query.setdefault('organization', project.quality_metrics_name)

        # Use an API connector object which provides the get_url method and
        # handles the actual request (also store a session) with paging support
        # Augment methods to collect more data beforehand which can be no-ops
        # for quality-time (api/navigation/*)

    def _format_version(self, date: datetime) -> Version:
        return {
            "version_id": self._format_date(date),
            "commit_date": format_date(date)
        }

    def get_versions(self, from_revision: Optional[Revision],
                     to_revision: Optional[Revision]) -> Sequence[Version]:
        # The data model contains no versioning and organization contents is
        # not able to be versioned, so we do not need to retrieve extra data
        # for intermediate versions.
        if to_revision is None:
            return [self.get_latest_version()]

        return [self._format_version(get_local_datetime(str(to_revision)))]

    def get_start_version(self) -> Optional[Version]:
        return self._format_version(self.START_DATE)

    def get_latest_version(self) -> Version:
        return self._format_version(datetime.now())

    @staticmethod
    def _format_date(date: datetime) -> str:
        return convert_local_datetime(date).isoformat()

    def get_paginated(self, merge_key: str, path: str = '',
                      query: DataUrl = None, paging: Optional[str] = 'paging',
                      size: int = 100) -> Dict[str, Any]:
        """
        Retrieve a SonarQube API response for a paginated entry point, making
        more requests to augment the paginated portion of each API response.
        The `merge_key` indicates the key of the JSON response that needs to
        the extended with more page data. The `path` is a path to the API route
        and `query` are additional query string parameters for the API route.
        The `paging` parameter is the key with the page metadata in the JSON
        response. If it is set to `None`, then the page metadata is part of the
        root dictionary. The `size` parameter is the number of items per page
        to obtain per API request.
        """

        limiter = Iterator_Limiter(size=size, maximum=10000)
        has_items = True
        if query is None:
            page_query = {}
        elif not isinstance(query, dict):
            page_query = dict(parse_qsl(query))
        else:
            page_query = query

        data = {}
        total = 0
        while limiter.check(has_items):
            page_query.update({
                'p': str(limiter.page),
                'ps': str(limiter.size)
            })
            url = self.get_url(path, page_query)
            request = self._session.get(url)
            request.raise_for_status()

            page_data = request.json()
            if limiter.page == 1:
                data = page_data
            else:
                data[merge_key].extend(page_data[merge_key])

            total += len(page_data[merge_key])
            if paging is None:
                paging_data = data
            else:
                paging_data = data[paging]
            has_items = int(paging_data['total']) > total
            limiter.update()

        return data

    def get_contents(self, version: Version) -> Dict[str, Any]:
        # Retrieve data about the components to consider
        # We may want to add more filters for shared instances
        try:
            query = {
                'f': '_all',
                's': 'analysisDate',
                'asc': 'no'
            }
            data = self.get_paginated('components',
                                      'api/components/search_projects', query)
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve metric defaults from Sonar") from error
        return data

    def get_data_model(self, version: Version) -> Dict[str, Any]:
        try:
            data = self.get_paginated('metrics', 'api/metrics/search', size=120)
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve metric defaults from Sonar") from error
        return data['metrics']

    def adjust_target_versions(self, version: Version, result: Dict[str, Any],
                               from_revision: Optional[Revision] = None) \
            -> List[Tuple[Version, Dict[str, Any]]]:
        # Quality gates are not versioned
        # Rules in quality profiles are (api/qualityprofiles/changelog),
        # but difficult to connect these to profile/gate metrics
        return [(version, result)]

    def get_measurements(self, metrics: Optional[MetricNames], version: Version,
                         from_revision: Optional[Revision] = None) \
            -> List[Dict[str, str]]:
        # api/measures/search_history for specific component identified within
        # the "metric_data" parameter?
        return []

    @property
    def filename(self) -> str:
        parts = urlsplit(self._url)
        query = parse_qs(parts.query)
        if 'id' in query and len(query['id']) == 1:
            return str(query['id'][0])

        return ''

    @property
    def parsers(self) -> Dict[str, Type[Parser]]:
        return {
            'project_meta': parser.Project_Parser
        }
