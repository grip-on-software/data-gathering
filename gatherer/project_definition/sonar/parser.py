"""
Module for parsing project definitions from SonarQube.

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

from typing import Any, Dict, List, Optional, Union
from ..base import Definition_Parser, Measurement_Parser, Metric_Parser, \
    MetricNameData, Version
from ...utils import parse_date

Component = Dict[str, Union[str, bool, List[str]]]

def _make_metric_name(metric_data: Dict[str, str], domain_name: str) -> str:
    return f"{metric_data['base_name']}_{domain_name}"

class Sonar_Definition_Parser(Definition_Parser):
    """
    Abstract SonarQube parser that makes use of several project definitions.
    """

    def __init__(self, version: Optional[Version] = None) -> None:
        super().__init__(version=version)
        self.organizations: List[Dict[str, str]] = []
        self.components: List[Component] = []
        self.data: Dict[str, Any] = {}

    def load_definition(self, filename: str, contents: Dict[str, Any]) -> None:
        try:
            self.organizations = contents.get("organizations", [])
            self.components = contents.get("components", [])
            if filename != '':
                self.components = [
                    component for component in self.components
                    if component.get("key") == filename
                ]
        except ValueError as error:
            raise RuntimeError(f"Could not parse JSON from {filename}: {error}") from error

    def parse(self) -> Dict[str, Any]:
        for index, component in enumerate(self.components):
            self.parse_component(index, component)

        return self.data

    def parse_component(self, index: int, component: Component) -> None:
        """
        Parse a component from a SonarQube server.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Project_Parser(Sonar_Definition_Parser):
    """
    A SonarQube project parser that retrieves the project name.
    """

    def parse(self) -> Dict[str, Any]:
        if self.organizations:
            self.data['quality_display_name'] = self.organizations[0]['name']
            return self.data

        return super().parse()

    def parse_component(self, index: int, component: Component) -> None:
        if index == 0:
            self.data['quality_display_name'] = str(component.get('name', ''))

class Sources_Parser(Sonar_Definition_Parser):
    """
    A SonarQube parser that extracts source URL from project components.
    """

    SOURCES_MAP = {
        'github': 'github',
        'azure': 'tfs',
        'gitlab': 'gitlab'
    }
    SOURCES_DOMAIN_FILTER: List[str] = []

    def parse_component(self, index: int, component: Component) -> None:
        # This actually needs the api/navigation/component details
        if "alm" not in component or not isinstance(component["alm"], dict):
            return

        name = str(component.get("name", component['key']))
        source = component["alm"]
        self.data.setdefault(name, {source['key']: [source['url']]})

class Measurements_Parser(Measurement_Parser):
    """
    A SonarQube parser that formats measurements of metrics in a standard
    table-like structure.
    """

    def parse(self) -> Dict[str, Any]:
        if self._measurements is None or self._version is None:
            return {}

        result = []
        for measurement in self._measurements:
            unique_metric_name = _make_metric_name(measurement,
                                                   measurement['domain_name'])
            row = self._parse_measurement(unique_metric_name, measurement,
                                          self._metrics.get(unique_metric_name))
            if row is not None:
                result.append(row)

        return {self._version['version_id']: result}

    @staticmethod
    def _parse_measurement(unique_metric_name: str, measurement: Dict[str, Any],
                           metric_data: MetricNameData = None) \
            -> Optional[Dict[str, str]]:
        measurement_value = str(measurement.get("value"))
        try:
            value = float(measurement_value)
        except ValueError:
            return None

        if metric_data is not None and 'target_value' in metric_data and \
            'direction' in metric_data:
            target = float(metric_data['target_value'])
            if 'perfect_value' in metric_data and \
                float(metric_data['perfect_value']) == value:
                category = 'perfect'
            else:
                green = target >= value \
                    if str(metric_data['direction']) == "-1" else \
                    target <= value
                category = 'green' if green else 'red'
        else:
            category = 'grey'

        return {
            'name': unique_metric_name,
            'base_name': measurement['base_name'],
            'domain_name': measurement['domain_name'],
            'value': measurement_value,
            'category': category,
            'date': parse_date(str(measurement.get("date")))
        }

class Metric_Defaults_Parser(Metric_Parser):
    """
    A SonarQube parser that extracts default metric properties from the data
    model, i.e., the list of metrics available on the instance.
    """

    SCALE_MAP: Dict[str, Union[str, Dict[str, str]]] = {
        'INT': 'count',
        'PERCENT': 'percentage',
        'WORK_DUR': {
            'scale': 'duration',
            'direction': '-1',
            'perfect_value': '0'
        },
        'RATING': {
            'scale': 'rating',
            'direction': '-1',
            'perfect_value': '1'
        }
    }

    def parse(self) -> Dict[str, Any]:
        if self._version is None:
            return {}

        result: List[Dict[str, str]] = []
        for metric in self._data_model.values():
            result.append(self._format_metric(metric, self._version))

        return {self._version['version_id']: result}

    def _format_metric(self, metric: Dict[str, Any], version: Version) \
            -> Dict[str, str]:
        metric_data = {
            "base_name": str(metric["key"]),
            "direction": "1" if metric.get("direction") == 1 else "-1"
        }

        scale = self.SCALE_MAP.get(metric.get("type", "INT"))
        if isinstance(scale, dict):
            metric_data.update(scale)
        elif scale is not None:
            metric_data['scale'] = scale

        metric_data.update(version)
        return metric_data

class Metric_Options_Parser(Metric_Defaults_Parser, Sonar_Definition_Parser):
    """
    A SonarQube parser that extracts targets for the metrics specified in the
    quality gate.
    """

    def parse(self) -> Dict[str, Any]:
        if self._version is None:
            return {}

        result: Dict[str, Dict[str, str]] = {}
        for metric in self._data_model.values():
            metric_data = self._format_metric(metric, self._version)
            # All metrics are default until we know if the targets are changed
            # in the quality profile
            metric_data["default"] = "1"

            # Make a domain-based metric for each component
            for component in self.components:
                domain_name = str(component['key'])
                unique_metric_name = _make_metric_name(metric_data, domain_name)
                metric_domain = metric_data.copy()
                metric_domain['domain_name'] = domain_name
                result[unique_metric_name] = metric_domain

        return result

    def parse_component(self, index: int, component: Component) -> None:
        pass
