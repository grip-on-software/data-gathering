"""
Data connection for project reports and metrics at a Quality-time server.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, \
    TYPE_CHECKING
from urllib.parse import urlsplit
import dateutil.parser
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from . import parser
from ..base import Data, DataUrl, Parser, MetricNames, MetricTargets, \
    Revision, Version, UUID
from ...request import Session
from ...table import Row
from ...utils import convert_local_datetime, convert_utc_datetime, \
    format_date, get_utc_datetime, parse_date
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from ...domain import Project, Source
else:
    Project = object
    Source = object

class Quality_Time_Data(Data):
    """
    Project definition stored on a Quality-time server as a JSON definition.
    """

    START_DATE = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
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
        'comment': 'comment',
        'scale': 'scale',
        'direction': 'direction'
    }

    def __init__(self, project: Project, source: Source, url: DataUrl = None):
        super().__init__(project, source, url)

        self._session = Session()
        self._session.verify = not source.get_option('unsafe_hosts')
        self._delta_description = re.compile(self.DELTA_DESCRIPTION, re.X)

    def _format_version(self, date: datetime) -> Row:
        return {
            "version_id": self._format_date(date),
            "commit_date": format_date(convert_local_datetime(date))
        }

    def get_versions(self, from_revision: Optional[Revision],
                     to_revision: Optional[Revision]) -> Sequence[Version]:
        # Internal report and datamodel APIs contain all the previous versions,
        # so we do not need to retrieve extra data for intermediate versions.
        if to_revision is None:
            return [self.get_latest_version()]

        return [self._format_version(get_utc_datetime(str(to_revision)))]

    def get_start_version(self) -> Optional[Version]:
        return self._format_version(self.START_DATE)

    def get_latest_version(self) -> Version:
        return self._format_version(datetime.now())

    @staticmethod
    def _format_date(date: datetime) -> str:
        return convert_utc_datetime(date).isoformat()

    def get_url(self, path: str = "reports", query: DataUrl = None,
                version: str = 'v3') -> str:
        """
        Format an API URL for the Quality-time server.
        """

        return super().get_url(f'/api/{version}/{path}', query=query)

    def get_contents(self, version: Version) -> Dict[str, Any]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url(f'report/{self.filename}',
                           {'report_date': self._format_date(date)},
                           version='internal')
        try:
            request = self._session.get(url)
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve reports") from error
        return request.json()

    def get_data_model(self, version: Version) -> Dict[str, Any]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url('datamodel',
                           {'report_date': self._format_date(date)},
                           version='internal')
        try:
            request = self._session.get(url)
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError("Could not retrieve data model") from error
        return request.json()

    def update_source_definitions(self, contents: Dict[str, Any]) -> None:
        pass

    def _get_changelog(self, metric: str, count: int, version: Version) \
            -> List[Dict[str, str]]:
        date = dateutil.parser.parse(version['version_id'])
        url = self.get_url(f'changelog/metric/{metric}/{count}',
                           {'report_date': self._format_date(date)},
                           version='internal')
        try:
            request = self._session.get(url)
            request.raise_for_status()
        except (ConnectError, HTTPError, Timeout) as error:
            raise RuntimeError(f"Could not retrieve changelog for {metric} from") \
                from error
        return request.json()['changelog']

    def adjust_target_versions(self, version: Version, result: Dict[str, Any],
                               from_revision: Optional[Revision] = None) \
            -> List[Tuple[Version, MetricTargets]]:
        if from_revision is not None:
            start_date = get_utc_datetime(parse_date(str(from_revision)))
        else:
            start_date = self.START_DATE
        versions = []
        for metric_uuid, metric in result.items():
            if start_date is not None and \
                get_utc_datetime(str(metric['report_date'])) <= start_date:
                continue

            changelog = self._get_changelog(metric_uuid, 10, version)
            versions.extend(self._adjust_changelog(changelog, start_date,
                                                   metric_uuid, metric))

        return sorted(versions, key=lambda version: version[0]['version_id'])

    def _adjust_changelog(self, changelog: List[Dict[str, str]],
                          start_date: datetime, metric_uuid: str,
                          metric: Row) -> List[Tuple[Version, MetricTargets]]:
        versions = []
        for change in changelog:
            match = self._delta_description.match(change.get("delta", ""))
            if match:
                delta = match.groupdict()
                key = str(delta['parameter_key'])
                if key not in self.METRIC_TARGET_MAP or \
                    self.METRIC_TARGET_MAP[key] not in metric:
                    continue

                date = get_utc_datetime(parse_date(change.get("timestamp", "")))
                if date <= start_date:
                    break

                versions.append(self._update_metric_version(metric_uuid,
                                                            metric, delta,
                                                            date, change))

        return versions

    def _update_metric_version(self, metric_uuid: str, metric: Row,
                               delta: Dict[str, str], date: datetime,
                               change: Dict[str, str]) \
            -> Tuple[Version, MetricTargets]:
        key = self.METRIC_TARGET_MAP[delta['parameter_key']]
        metric[key] = delta['new_value']
        new_version = self._format_version(date)
        new_version.update({
            'developer': delta['user'],
            'email': change.get('email', '0'),
            'message': ''
        })
        new_result = {metric_uuid: metric.copy()}
        metric[key] = delta['old_value']
        return (new_version, new_result)

    def get_measurements(self, metrics: Optional[MetricNames], version: Version,
                         from_revision: Optional[Revision] = None) -> List[Row]:
        if metrics is None:
            raise RuntimeError('No metric names available for measurements')

        date = version['version_id']
        if from_revision is not None:
            cutoff = get_utc_datetime(parse_date(str(from_revision)))
        else:
            cutoff = self.START_DATE

        result: List[Row] = []
        for metric in metrics:
            if not UUID.match(metric):
                continue

            url = self.get_url(f'measurements/{metric}', {'report_date': date},
                               version='internal')
            try:
                request = self._session.get(url)
                request.raise_for_status()
            except (ConnectError, HTTPError, Timeout) as error:
                raise RuntimeError(f"Could not retrieve measurements for {metric}") \
                    from error

            for measurement in request.json()['measurements']:
                measurement_date = parse_date(str(measurement.get("end")))
                if get_utc_datetime(measurement_date) > cutoff:
                    result.append(measurement)

        return result

    @property
    def filename(self) -> str:
        parts = urlsplit(self._url)
        path = parts.path.lstrip('/')
        if UUID.match(path):
            return path

        return ''

    @property
    def parsers(self) -> Dict[str, Type[Parser]]:
        return {
            'project_meta': parser.Project_Parser,
            'project_sources': parser.Sources_Parser,
            'measurements': parser.Measurements_Parser,
            'metric_defaults': parser.Metric_Defaults_Parser,
            'metric_options': parser.Metric_Options_Parser
        }
