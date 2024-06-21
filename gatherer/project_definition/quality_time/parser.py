"""
Module for parsing report definitions from Quality-time.

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

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Union
from ..base import Definition_Parser, Measurement_Parser, Metric_Parser, \
    MetricNameData, SourceUrl, Version, UUID
from ...utils import convert_local_datetime, format_date

Source = Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]
Metric = Dict[str, Optional[Union[str, Dict[str, Source]]]]
Subject = Dict[str, Union[str, Dict[str, Metric]]]
Report = Dict[str, Union[str, Dict[str, Subject]]]
Measurement = Dict[str, Union[str, Dict[str, Optional[str]]]]
Metrics = Dict[str, Dict[str, str]]

class Quality_Time_Report_Parser(Definition_Parser):
    """
    Abstract Quality-time parser that makes use of several reports.
    """

    def __init__(self, version: Optional[Version] = None) -> None:
        super().__init__(version=version)
        self.reports: List[Report] = []
        self.data: Dict[str, Any] = {}

    def load_definition(self, filename: str, contents: Dict[str, Any]) -> None:
        try:
            self.reports = contents.get("reports", [])
            if UUID.match(filename):
                self.reports = [
                    report for report in self.reports
                    if report.get("report_uuid") == filename
                ]
        except ValueError as error:
            raise RuntimeError(f"Could not parse JSON from {filename}: {error}") from error

    def parse(self) -> Dict[str, Any]:
        for index, report in enumerate(self.reports):
            self.parse_report(index, report)

        return self.data

    def parse_report(self, index: int, report: Report) -> None:
        """
        Parse a single report from a Quality-time server.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Project_Parser(Quality_Time_Report_Parser):
    """
    A Quality-time report parser that retrieves the project name.
    """

    def parse_report(self, index: int, report: Report) -> None:
        if index == 0:
            self.data['quality_display_name'] = report.get("title", "")

class Sources_Parser(Quality_Time_Report_Parser):
    """
    A Quality-time parser that extracts source URLs for the metrics specified in
    the report.
    """

    SOURCES_MAP = {
        'gitlab': 'gitlab',
        'azure_devops': 'tfs',
        'sonarqube': 'sonar',
        'jenkins': 'jenkins',
        'jira': 'jira',
        'quality_time': 'quality-time'
    }
    PATH_PARAMETERS: Dict[str, Sequence[str]] = {
        'project': (),
        'repository': ('_git',)
    }
    SOURCE_ID_PARAMETERS = ('component',)
    SOURCES_DOMAIN_FILTER: List[str] = []

    def parse_report(self, index: int, report: Report) -> None:
        subjects = report.get("subjects", {})
        if not isinstance(subjects, dict):
            return

        for subject_uuid, subject in subjects.items():
            if not isinstance(subject, dict):
                continue

            name = str(subject.get("name", subject_uuid))
            self.data.setdefault(name, self._parse_sources(subject))

    def _parse_sources(self, subject: Subject) -> Dict[str, Set[SourceUrl]]:
        subject_type = str(subject.get("type", ""))
        sources: Dict[str, Set[SourceUrl]] = {}
        metrics = subject.get("metrics", {})
        if not isinstance(metrics, dict):
            return sources

        for metric in metrics.values():
            metric_sources = metric.get("sources")
            if not isinstance(metric_sources, dict):
                continue

            for metric_source in metric_sources.values():
                source_type = str(metric_source.get("type", ""))
                sources.setdefault(source_type, set())
                source = self._parse_source(subject_type, metric_source)
                if source is not None:
                    sources[source_type].add(source)

        return sources

    def _parse_source(self, subject_type: str, source: Source) \
            -> Optional[SourceUrl]:
        parameters = source.get("parameters")
        if not isinstance(parameters, dict):
            return None

        source_url = parameters.get("url")
        if not isinstance(source_url, str):
            return None

        for parameter, parts in self.PATH_PARAMETERS.items():
            if parameter in parameters:
                url_parts = (source_url.rstrip("/"),) + tuple(parts) + \
                    (str(parameters[parameter]),)
                source_url = "/".join(url_parts)

        for parameter in self.SOURCE_ID_PARAMETERS:
            if parameter in parameters:
                return (source_url, str(parameters[parameter]), subject_type)

        return source_url

class Measurements_Parser(Measurement_Parser):
    """
    A Quality-time parser that formats measurements of metrics in a standard
    table-like structure.
    """

    def parse(self) -> Dict[str, Any]:
        if self._measurements is None or self._version is None:
            return {}

        result = []
        for measurement in self._measurements:
            metric = str(measurement.pop('metric_uuid'))
            row = self._parse_measurement(metric, measurement,
                                          self._metrics.get(metric))
            if row is not None:
                result.append(row)

        return {self._version['version_id']: result}

    @staticmethod
    def _parse_measurement(metric_uuid: str, measurement: Measurement,
                           metric_data: MetricNameData = None) \
            -> Optional[Dict[str, str]]:
        """
        Parse a measurement of a Quality-time metric from its API.
        """

        if metric_data is not None:
            scale = str(metric_data.get("scale", "count"))
        else:
            scale = "count"

        count = measurement.get(scale, {})
        if isinstance(count, dict):
            category = count.get("status")
            value = count.get("value")
        else:
            category = None
            value = None

        if value is not None:
            # Ignore values that are not parseable, such as version numbers
            try:
                int(value)
            except ValueError:
                return None

        date = datetime.fromisoformat(str(measurement['end']))
        since_date = datetime.fromisoformat(str(measurement['start']))

        return {
            'name': metric_uuid,
            'value': str(value) if value is not None else "-1",
            'category': str(category) if category is not None else "unknown",
            'date': format_date(convert_local_datetime(date)),
            'since_date': format_date(convert_local_datetime(since_date))
        }

class Metric_Defaults_Parser(Metric_Parser):
    """
    A Quality-time parser that extracts default metric properties from the
    data model.
    """

    def parse(self) -> Dict[str, Any]:
        if self._version is None:
            return {}

        result = []
        metrics: Metrics = self._data_model.get("metrics", {})

        timestamp = str(self._data_model.get("timestamp",
                                             self._version['version_id']))
        date = datetime.fromisoformat(timestamp)
        commit_date = format_date(convert_local_datetime(date))

        for metric_type, metric in metrics.items():
            result.append({
                "base_name": metric_type,
                "version_id": timestamp,
                "commit_date": commit_date,
                "direction": "1" if metric.get("direction") == ">" else "-1",
                "target_value": metric.get("target"),
                "low_target_value": metric.get("near_target"),
                "scale": metric.get("default_scale", "count")
            })

        return {self._version['version_id']: result}

class Metric_Options_Parser(Metric_Parser, Quality_Time_Report_Parser):
    """
    A Quality-time parser that extracts targets from the metrics specified in
    the report.
    """

    def parse_report(self, index: int, report: Report) -> None:
        metrics: Metrics = self._data_model.get("metrics", {})
        report_uuid = str(report.get("report_uuid", ""))

        date = datetime.fromisoformat(str(report.get("timestamp", "")))
        report_date = format_date(convert_local_datetime(date))

        subjects = report.get("subjects", {})
        if not isinstance(subjects, dict):
            return

        for name, subject in subjects.items():
            if not isinstance(subject, dict):
                continue

            self._parse_subject(metrics, name, subject, report_uuid,
                                report_date)

    def _parse_subject(self, metrics: Metrics, name: str, subject: Subject,
                       report_uuid: str, report_date: str) -> None:
        subject_name = str(subject.get("name", name))
        subject_type = str(subject.get("type", "software"))
        report_metrics = subject.get("metrics", {})
        if not isinstance(report_metrics, dict):
            return

        for metric_uuid, metric in report_metrics.items():
            metric_data = self._parse_metric(metric, subject_name, metrics)
            metric_data.update({
                "report_uuid": report_uuid,
                "report_date": report_date,
                "domain_type": subject_type
            })

            self.data[metric_uuid] = metric_data

    @staticmethod
    def _parse_metric(metric: Metric, subject_name: str, metrics: Metrics) \
            -> Dict[str, str]:
        comment = metric.get("comment", None)
        debt_target = metric.get("debt_target", None)
        near_target = str(metric.get("near_target", ""))
        if near_target == "":
            near_target = "0"
        target = str(metric.get("target"))
        if target == "":
            target = "0"

        metric_type = str(metric.get("type", ""))
        metric_sources = metric.get("sources", {})
        model = metrics.get(metric_type, {})

        metric_data = {
            "base_name": metric_type,
            "domain_name": subject_name,
            "scale": str(metric.get("scale", "count")),
            "number_of_sources": str(len(metric_sources)) \
                if isinstance(metric_sources, dict) else "0"
        }
        if comment is None and debt_target is None and \
            metric.get("direction") == model.get("direction") and \
            target == str(model.get("target", "0")) and \
            near_target == str(model.get("near_target", "0")):
            metric_data["default"] = "1"
        else:
            metric_data.update({
                "low_target": near_target,
                "target": target,
                "debt_target": "" if debt_target is None else str(debt_target),
                "direction": "1" if metric.get("direction") == ">" else "-1",
                "comment": "" if comment is None else str(comment),
            })

        return metric_data
