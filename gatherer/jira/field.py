"""
Field definitions that fetch fields from JIRA API issue results.

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

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from jira import Issue
from .base import Base_Jira_Field, Base_Changelog_Field, TableKey
from .parser import Field_Parser
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira, FieldValue
else:
    Jira = object
    FieldValue = object

###
# Field definitions
###

class Jira_Field(Base_Jira_Field):
    """
    Field parser for the issue field data returned by the JIRA REST API.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        """
        Retrieve the raw data from the issue.

        This method is responsible for determining the correct field to use, and
        to preprocess it as much as possible (such as extracting an ID from its
        subproperties). The returned value is not yet parsed according to the
        type of the field.
        """

        raise NotImplementedError("Subclasses must extend this method")

    def parse(self, issue: Any) -> Optional[str]:
        """
        Retrieve the field from the issue and parse it so that it receives the
        correct type and format.
        """

        field = self.fetch(issue)
        return self.cast(field)

    def cast(self, field: Optional[str]) -> Optional[str]:
        """
        Use the appropriate type cast to convert the fetched field to a string
        representation of the field.
        """

        for parser in self.get_types():
            field = parser.parse(field)

        return field

    def get_types(self) -> List[Field_Parser]:
        """
        Retrieve the type parsers that this field uses in sequence to perform
        its type casting actions.
        """

        if "type" in self.data:
            if not isinstance(self.data["type"], str):
                types = tuple(self.data["type"])
            else:
                types = (self.data["type"],)

            return [self.jira.get_type_cast(datatype) for datatype in types]

        return []

    @property
    def table_name(self) -> Optional[str]:
        # If this field wishes to have a table, then default to the field name.
        # Jira.register_table overrides this with the table name provided in
        # the field specification data if possible.
        if "table" in self.data:
            return self.name

        return None

class Primary_Field(Jira_Field):
    """
    A field in the JIRA response that contains primary information of the issue,
    such as the ID or key of the issue.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        return getattr(issue, str(self.data["primary"]))

    @property
    def search_field(self) -> Optional[str]:
        return None

    @property
    def table_key(self) -> TableKey:
        raise Exception(f"Primary field '{self.name}' is not keyable at this moment")

class Payload_Field(Jira_Field):
    """
    A field in the JIRA's main payload response, which are the editable fields
    as well as metadata fields for the issue.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        if hasattr(issue.fields, str(self.data["field"])):
            return getattr(issue.fields, str(self.data["field"]))

        return None

    @property
    def search_field(self) -> Optional[str]:
        return str(self.data["field"])

    @property
    def table_key(self) -> TableKey:
        return "id"

class Property_Field(Payload_Field):
    """
    A field in the JIRA's main payload response of which one property is the
    identifying value for that field in the issue.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        field = super().fetch(issue)
        if hasattr(field, str(self.data["property"])):
            return getattr(field, str(self.data["property"]))

        return None

    def parse(self, issue: Any) -> Optional[str]:
        field = super().parse(issue)
        if field is None:
            return None

        if "table" in self.data and isinstance(self.data["table"], dict):
            payload_field = super().fetch(issue)
            row: Dict[str, str] = {}
            row[str(self.data["property"])] = field
            has_data = False
            for name, datatype in self.data["table"].items():
                row[name] = str(0)
                if hasattr(payload_field, name):
                    has_data = True
                    prop = getattr(payload_field, name)
                    parser = self.jira.get_type_cast(str(datatype))
                    value = parser.parse(prop)
                    if value is not None:
                        row[name] = value

            if has_data:
                self.jira.get_table(self.name).append(row)

        return field

    @property
    def table_key(self) -> TableKey:
        return str(self.data["property"])

class Changelog_Primary_Field(Jira_Field, Base_Changelog_Field):
    """
    A field in the change items in the changelog of the JIRA response.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        if hasattr(issue, str(self.data["changelog_primary"])):
            return getattr(issue, str(self.data["changelog_primary"]))

        return None

    def parse_changelog(self, entry: Any, diffs: Dict[str, Optional[str]],
                        issue: Issue) -> Optional[str]:
        return self.parse(entry)

    @property
    def search_field(self) -> Optional[str]:
        return None

    @property
    def table_key(self) -> TableKey:
        raise Exception("Changelog fields are not keyable at this moment")

class Changelog_Field(Jira_Field, Base_Changelog_Field):
    """
    A field in the changelog items of the JIRA expanded response.
    """

    def fetch(self, issue: Any) -> Optional[str]:
        data = issue.__dict__
        if data['from'] is not None:
            return data['from']
        if data['fromString'] is not None:
            return data['fromString']

        return None

    def parse_changelog(self, entry: Any, diffs: Dict[str, Optional[str]],
                        issue: Issue) -> Optional[str]:
        """
        Parse changelog information from a changelog entry.
        """

        field = self.parse(entry)
        for parser in self.get_types():
            field = parser.parse_changelog(entry.__dict__, field, diffs)

        return field

    @property
    def search_field(self) -> Optional[str]:
        return None

    @property
    def table_key(self) -> TableKey:
        raise Exception("Changelog fields are not keyable at this moment")
