"""
Module for parsing report definitions from Quality Time.
"""

import json
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urljoin
from .base import SourceUrl, Definition_Parser
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
        self.json: Dict[str, Any] = {}
        self.data: Dict[str, Any] = {}

    def load_definition(self, filename: str, contents: Union[str, bytes]) -> None:
        try:
            self.json = json.loads(contents)
        except ValueError as error:
            raise RuntimeError(f"Could not parse JSON from {filename}: {error}")

    def parse(self) -> Dict[str, Any]:
        for index, report in enumerate(self.json.get("reports", [])):
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
    PATH_PARAMETERS = ('project',)
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

        for parameter in self.PATH_PARAMETERS:
            if parameter in parameters:
                source_url = urljoin(source_url, parameters[parameter])

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
            metrics = subject.get("metrics", {})
            if not isinstance(metrics, dict):
                continue

            for uuid, metric in metrics.items():
                metric_data = self._parse_metric(metric, subject_name, metrics)
                metric_data.update({
                    "report_uuid": report_uuid,
                    "report_date": parse_date(report_date)
                })

                self.data[uuid] = metric_data

    @staticmethod
    def _parse_metric(metric: Dict[str, Optional[str]], subject_name: str,
                      metrics: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        comment = metric.get("comment", None)
        debt_target = metric.get("debt_target", None)
        near_target = str(metric.get("near_target", "0"))
        target = str(metric.get("target", "0"))
        metric_type = str(metric.get("type", ""))
        model = metrics.get(metric_type, {})

        metric_data = {
            "base_name": metric_type,
            "domain_name": subject_name
        }
        if comment is None and debt_target is None and \
            target == model.get("target", "") and \
            near_target == model.get("near_target", ""):
            metric_data["default"] = "1"
        else:
            metric_data.update({
                "low_target": near_target,
                "target": target,
                "debt_target": "" if debt_target is None else str(debt_target),
                "comment": "" if comment is None else str(comment),
            })

        return metric_data
