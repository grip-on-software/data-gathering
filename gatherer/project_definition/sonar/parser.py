"""
Module for parsing project definitions from SonarQube.

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

from typing import Any, Dict, List, Optional, Union
from ..base import Definition_Parser, Version

Component = Dict[str, Union[str, bool, List[str]]]

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
