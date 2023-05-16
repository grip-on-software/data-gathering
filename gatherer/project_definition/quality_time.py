"""
Module for parsing report definitions from Quality Time.

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

import json
from typing import Any, Dict, List, Optional, Sequence, Set, Union
from .base import SourceUrl, Definition_Parser, UUID
from ..utils import parse_date

Source = Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]
Metric = Dict[str, Union[str, Dict[str, Source]]]
Subject = Dict[str, Union[str, Dict[str, Metric]]]
Report = Dict[str, Union[str, Dict[str, Subject]]]
# Dict[str, str], Dict[str, int], Dict[str, Dict[str, int]]

class Quality_Time_Parser(Definition_Parser):
    """
    Abstract Quality Time parser.
    """

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.reports: List[Report] = []
        self.data: Dict[str, Any] = {}

    def load_definition(self, filename: str, contents: Union[str, bytes]) -> None:
        try:
            definition = json.loads(contents)
            self.reports = definition.get("reports", [])
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
        Parse a single report from a Quality Time server.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Project_Parser(Quality_Time_Parser):
    """
    A Quality Time report parser that retrieves the project name.
    """

    def parse_report(self, index: int, report: Report) -> None:
        if index == 0:
            self.data['quality_display_name'] = report.get("title", "")

class Sources_Parser(Quality_Time_Parser):
    """
    A Quality Time parser that extracts source URLs for the metrics specified in
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
            metric_sources = metric.get("sources", {})
            if not isinstance(metric_sources, dict):
                continue

            for metric_source in metric_sources.values():
                source_type = str(metric_source.get("type", ""))
                sources.setdefault(source_type, set())
                source = self._parse_source(subject_type, metric_source)
                if source is not None:
                    sources[source_type].add(source)

        return sources

    def _parse_source(self, subject_type: str, source: Dict[str, Any]) -> Optional[SourceUrl]:
        parameters: Dict[str, str] = source.get("parameters", {})
        source_url: str = parameters.get("url", "")
        if source_url == "":
            return None

        for parameter, parts in self.PATH_PARAMETERS.items():
            if parameter in parameters:
                url_parts = (source_url.rstrip("/"),) + tuple(parts) + (parameters[parameter],)
                source_url = "/".join(url_parts)

        for parameter in self.SOURCE_ID_PARAMETERS:
            if parameter in parameters:
                return (source_url, parameters[parameter], subject_type)

        return source_url

class Metric_Options_Parser(Quality_Time_Parser):
    """
    A Quality Time parser that extracts targets from the metrics specified in
    the report.
    """

    def __init__(self, data_model: Optional[Dict[str, Any]] = None,
                 **options: Any) -> None:
        super().__init__(**options)
        if data_model is None:
            self._data_model: Dict[str, Any] = {}
        else:
            self._data_model = data_model

    def parse_report(self, index: int, report: Dict[str, Any]) -> None:
        metrics = self._data_model.get("metrics", {})
        report_uuid = str(report.get("report_uuid", ""))
        report_date = str(report.get("timestamp", ""))
        subjects = report.get("subjects", {})
        if not isinstance(subjects, dict):
            return

        for name, subject in subjects.items():
            if not isinstance(subject, dict):
                continue

            subject_name = subject.get("name", name)
            subject_type = subject.get("type", "software")
            metrics = subject.get("metrics", {})
            if not isinstance(metrics, dict):
                continue

            for uuid, metric in metrics.items():
                metric_data = self._parse_metric(metric, subject_name, metrics)
                metric_data.update({
                    "report_uuid": report_uuid,
                    "report_date": parse_date(report_date),
                    "domain_type": subject_type
                })

                self.data[uuid] = metric_data

    @staticmethod
    def _parse_metric(metric: Dict[str, Optional[Union[str, Dict[str, Any]]]],
                      subject_name: str,
                      metrics: Dict[str, Dict[str, str]]) -> Dict[str, str]:
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
            "number_of_sources": str(len(metric_sources)) \
                if isinstance(metric_sources, dict) else "0"
        }
        if comment is None and debt_target is None and \
            target == str(model.get("target", "0")) and \
            near_target == str(model.get("near_target", "0")):
            metric_data["default"] = "1"
        else:
            metric_data.update({
                "low_target": near_target,
                "target": target,
                "debt_target": "" if debt_target is None else str(debt_target),
                "comment": "" if comment is None else str(comment),
            })

        return metric_data
