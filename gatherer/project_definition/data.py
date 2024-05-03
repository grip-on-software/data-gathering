"""
Data connection for the project definitions.

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
import re
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Type, \
    Union, TYPE_CHECKING
from urllib.parse import urlsplit
import dateutil.parser
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from .base import Data, DataUrl, Definition_Parser, UUID
from . import quality_time
from ..request import Session
from ..utils import convert_local_datetime, convert_utc_datetime, format_date, \
    get_utc_datetime, parse_date
from ..version_control.repo import Version
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ..domain import Project, Source
else:
    Project = object
    Source = object

class Quality_Time_Data(Data):
    """
    Project definition stored on a Quality Time server as a JSON definition.
    """

    LATEST_VERSION = '3000-01-31T23:00:00.0000Z'
    DELTA_DESCRIPTION = r"""
        (?P<user>.*) \s changed \s the \s (?P<parameter_key>.*) \s of \s
        metric \s '(?P<metric_name>.*)' \s of \s subject \s
        '(?P<subject_name>.*)' \s in \s report \s '(?P<report_name>.*)' \s
        from \s '(?P<old_value>.*)' \s to \s '(?P<new_value>.*)'.
        """
    METRIC_TARGET_MAP = {
        'near_target': 'low_target',
        'target': 'target',
        'debt_target': 'debt_target',
        'comment': 'comment'
    }

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url)

        self._session = Session()
        self._session.verify = not source.get_option('unsafe_hosts')
        self._delta_description = re.compile(self.DELTA_DESCRIPTION, re.X)

    @staticmethod
    def _format_version(date: str) -> Dict[str, str]:
        return {
            "version_id": date,
            "commit_date": date
        }

    def get_versions(self, from_revision: Optional[Version],
                     to_revision: Optional[Version]) -> Iterable[Dict[str, str]]:
        if to_revision is None:
            return [self.get_latest_version()]

        return [self._format_version(str(to_revision))]

    def get_latest_version(self) -> Dict[str, str]:
        date = self._format_date(datetime.now())
        return self._format_version(date)

    @staticmethod
    def _format_date(date: datetime) -> str:
        return convert_utc_datetime(date).isoformat()

    def get_url(self, path: str = "reports", query: DataUrl = None) -> str:
        """
        Format an API URL for the Quality Time server.
        """

        return super().get_url(f'/api/v3/{path}', query=query)

    def get_contents(self, version: Dict[str, str]) -> Union[str, bytes]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url('reports', {'report_date': self._format_date(date)})
        request = self._session.get(url)
        try:
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve reports from Quality Time") from error
        return request.text

    def get_data_model(self, version: Dict[str, str]) -> Dict[str, Any]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url('datamodel',
                           {'report_date': self._format_date(date)})
        request = self._session.get(url)
        try:
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve data model from Quality Time") from error
        return request.json()

    def _get_changelog(self, metric: str, count: int, version: Dict[str, str]) \
            -> List[Dict[str, str]]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url(f'changelog/metric/{metric}/{count}',
                           {'report_date': self._format_date(date)})
        request = self._session.get(url)
        try:
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError(f"Could not retrieve changelog for {metric} from Quality Time") \
                from error
        return request.json()['changelog']

    def adjust_target_versions(self, version: Dict[str, str],
                               result: Dict[str, Any],
                               start_version: Optional[Version]) \
            -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
        start_date = get_utc_datetime(parse_date(str(start_version)))
        versions = []
        for metric_uuid, metric in result.items():
            if get_utc_datetime(metric['report_date']) <= start_date:
                continue

            changelog = self._get_changelog(metric_uuid, 10, version)
            versions.extend(self._adjust_changelog(changelog, start_date,
                                                   metric_uuid, metric))

        return sorted(versions, key=lambda version: version[0]['version_id'])

    def _adjust_changelog(self, changelog: List[Dict[str, str]],
                          start_date: datetime, metric_uuid: str,
                          metric: Dict[str, str]) \
            -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
        versions = []
        for change in changelog:
            match = self._delta_description.match(change.get("delta", ""))
            if match:
                delta = match.groupdict()
                key = delta['parameter_key']
                if key not in self.METRIC_TARGET_MAP or \
                    self.METRIC_TARGET_MAP[key] not in metric:
                    continue

                date = get_utc_datetime(parse_date(change.get("timestamp", "")))
                if date <= start_date:
                    break

                versions.append(self._update_metric_version(metric_uuid,
                                                            metric, delta,
                                                            date))

        return versions

    def _update_metric_version(self, metric_uuid: str, metric: Dict[str, str],
                               delta: Dict[str, str], utc_date: datetime) \
            -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
        key = self.METRIC_TARGET_MAP[delta['parameter_key']]
        metric[key] = delta['new_value']
        local_date = convert_local_datetime(utc_date)
        new_version = self._format_version(format_date(local_date))
        new_version.update({
            'developer': delta['user'],
            'message': ''
        })
        new_result = {metric_uuid: metric.copy()}
        metric[key] = delta['old_value']
        return (new_version, new_result)

    def get_measurements(self, metric: str, version: Dict[str, str],
                         cutoff_date: Optional[datetime] = None) \
            -> Iterator[Dict[str, str]]:
        date = version['version_id']
        url = self.get_url(f'measurements/{metric}', {'report_date': date})
        request = self._session.get(url)
        request.raise_for_status()
        for measurement in request.json()['measurements']:
            data = self._parse_measurement(metric, measurement, cutoff_date)
            if data is not None:
                yield data

    @staticmethod
    def _parse_measurement(metric_uuid: str, measurement: Dict[str, Any],
                           cutoff_date: Optional[datetime]) \
            -> Optional[Dict[str, str]]:
        """
        Parse a measurement of a Quality Time metric from its API.
        """

        date = parse_date(str(measurement.get("end")))
        if cutoff_date is not None and get_utc_datetime(date) <= cutoff_date:
            return None

        count = measurement.get("count", {})
        category = count.get("status")
        value = count.get("value")

        return {
            'name': metric_uuid,
            'value': str(value) if value is not None else "-1",
            'category': str(category) if category is not None else "unknown",
            'date': date,
            'since_date': parse_date(str(measurement.get("start")))
        }

    @property
    def filename(self) -> str:
        parts = urlsplit(self._url)
        path = parts.path.lstrip('/')
        if UUID.match(path):
            return path

        return ''

    @property
    def parsers(self) -> Dict[str, Type[Definition_Parser]]:
        return {
            'project_meta': quality_time.Project_Parser,
            'project_sources': quality_time.Sources_Parser,
            'metric_options': quality_time.Metric_Options_Parser
        }
