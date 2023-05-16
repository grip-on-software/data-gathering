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
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, Union
from urllib.parse import urlencode, urlsplit, urlunsplit
import dateutil.parser
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from .base import Data, Definition_Parser, UUID
from . import parser, quality_time
from ..config import Configuration
from ..domain import Project, Source
from ..request import Session
from ..utils import convert_local_datetime, convert_utc_datetime, format_date, \
    get_utc_datetime, parse_date
from ..version_control.repo import PathLike, Version

class Project_Definition_Data(Data):
    """
    Project definition stored as a Python file in a version control system.
    """

    DEFINITION_FILENAME = 'project_definition.py'

    def __init__(self, project: Project, source: Source,
                 repo_path: Optional[PathLike] = None):
        self._project = project
        quality_name = project.quality_metrics_name
        if quality_name is None:
            raise RuntimeError(f'No project definitions for {project.key}')

        if source.repository_class is not None:
            if repo_path is None:
                repo_path = str(project.get_key_setting('definitions', 'path',
                                                        quality_name))

            repo_class = source.repository_class
            self._repo = repo_class(source, repo_path, project=project)

            if self._repo.is_empty():
                raise RuntimeError(f'Project definitions repository for '
                                   f'{project.key} at {repo_path} is empty; '
                                   f'must be checked out first')

            if quality_name not in str(repo_path):
                self._filename = f'{quality_name}/{self.DEFINITION_FILENAME}'
            else:
                self._filename = self.DEFINITION_FILENAME

    def get_versions(self, from_revision: Optional[Version],
                     to_revision: Optional[Version]) -> Iterable[Dict[str, str]]:
        return self._repo.get_versions(self._filename,
                                       from_revision=from_revision,
                                       to_revision=to_revision,
                                       descending=False, stats=False)

    def get_latest_version(self) -> Dict[str, str]:
        return {"version_id": str(self._repo.get_latest_version())}

    def get_contents(self, version: Dict[str, str]) -> Union[str, bytes]:
        return self._repo.get_contents(self._filename,
                                       revision=version['version_id'])

    def get_data_model(self, version: Dict[str, str]) -> Dict[str, Any]:
        return {}

    def adjust_target_versions(self, version: Dict[str, str],
                               result: Dict[str, Any],
                               start_version: Optional[Version]) \
            -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
        return [(version, result)]

    @property
    def path(self) -> str:
        repo_path = self._repo.repo_directory
        if self._project.quality_metrics_name is not None and \
            self._project.quality_metrics_name in str(repo_path):
            return str(repo_path.resolve().parent)

        return str(repo_path)

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def parsers(self) -> Dict[str, Type[Definition_Parser]]:
        return {
            'project_meta': parser.Project_Parser,
            'project_sources': parser.Sources_Parser,
            'metric_options': parser.Metric_Options_Parser
        }

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

    def __init__(self, project: Project, source: Source,
                 url: Optional[PathLike] = None):
        self._project = project
        if url is not None and not isinstance(url, os.PathLike):
            self._url = url
        else:
            self._url = source.plain_url

        if Configuration.is_url_blacklisted(self._url):
            raise RuntimeError(f'Cannot use blacklisted URL as a definitions source: {self._url}')

        verify: Union[Optional[str], bool] = source.get_option('verify')
        if verify is None:
            verify = True
        self._session = Session()
        self._session.verify = verify
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

    def get_url(self, path: str = "reports",
                query: Optional[Dict[str, str]] = None) -> str:
        """
        Format an API URL for the Quality Time server.
        """

        parts = urlsplit(self._url)
        query_string = ""
        if query is not None:
            query_string = urlencode(query)
        new_parts = (parts.scheme, parts.hostname, f'/api/v3/{path}',
                     query_string, '')
        return urlunsplit(new_parts)

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

    def get_measurements(self, metric_uuid: str, version: Dict[str, str]) \
            -> List[Dict[str, Any]]:
        """
        Retrieve the measurements for a specific metric up to a certain date.
        """

        date = version['version_id']
        url = self.get_url(f'measurements/{metric_uuid}', {'report_date': date})
        request = self._session.get(url)
        request.raise_for_status()
        return request.json()['measurements']

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
