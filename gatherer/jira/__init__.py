"""
Package for classes and utilities related to extracting data from the JIRA API.

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
import logging
import os
import re
from copy import copy
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from jira import Issue, JIRA, JIRAError
from .base import Base_Jira_Field, Table_Source
from .changelog import Changelog
from .field import Jira_Field, Primary_Field, Payload_Field, Property_Field
from .parser import Field_Parser, Int_Parser, String_Parser, Boolean_Parser, \
    Date_Parser, Unicode_Parser, Sprint_Parser, Developer_Parser, \
    Decimal_Parser, ID_Parser, ID_List_Parser, Version_Parser, Rank_Parser, \
    Issue_Key_Parser, Flag_Parser, Ready_Status_Parser, Labels_Parser, \
    Project_Parser, Status_Category_Parser
from .query import Query
from .special_field import Special_Field
from .update import Updated_Time, Update_Tracker
from ..table import Table, Key_Table, Link_Table
from ..domain import Project, source

Data = Dict[str, str]
FieldValue = Union[str, List[str], Dict[str, Union[str, bool]]]
Field = Dict[str, FieldValue]
Prefetcher = Callable[[Query], None]

__all__ = ["Jira"]

class Jira:
    """
    JIRA parser and extraction tool.

    This class extracts fields from JIRA according to a field specification.

    Each field has a dictionary of configuration. Each field can have at most
    one of the following, although this is not required if the field only
    exists within the changelog:
    - "primary": If given, the property name of the field within the main
      issue's response data.
    - "field": If given, the property name within the "fields" dictionary
      of the issue.
    - "special_parser": If given, the name of the table used for this field.
      The field itself lives within the main issue's response data and uses the
      field key for retrieval, if possible. A special field parser needs to
      perform all the fetching, parsing and table addition by itself.

    If the field has a "field" key, then the following setting is accepted:
    - "property": If given, the property name within the dictionary
      pointed at by "field".

    Additionally, fields may have at most one of the following settings:
    - "changelog_primary": The name of the field within the main changelog
      holder.
    - "changelog_name": The name of the field within one change.

    All kinds of fields may have the following settings:
    - "type": The type of the field value, see Jira.type_casts keys for values.
      This is the type as it will be stored in the exported issues data. It is
      independent from other data relevant to that field, i.e., for "property"
      fields it is the type of that property. The type cast parser classes
      ensure that we convert to strings correctly. Can have multiple types
      in a tuple, which are applied in order.
    - "table": Either the name of a table to store additional data in, or
      the specification of a table using property names and type cast parsers.
      In the former situation, the table configuration (e.g. key) is defined by
      the field type object or the (special) parser used, while the latter
      is only used when the field is a property field whose property is used
      as the main key.

    The specification may also include any other keys and values, which are
    supplied to the fields, parsers and special field parsers. For example,
    the comment field has a "fields" mapping for its properties and exported
    subfield names.

    Fields that are retrieved or deduced from only changelog data are those
    without "primary" or "field", i.e., "changelog_id" and "updated_by".
    """

    # JIRA field specification keys and their associated field parsers.
    # The fields are tried in order to determine the best fit parser.
    FIELD_PARSERS: List[Tuple[str, Type[Base_Jira_Field]]] = [
        ("primary", Primary_Field),
        ("property", Property_Field),
        ("field", Payload_Field)
    ]

    def __init__(self, project: Project, updated_since: str) -> None:
        self._project = project
        self._updated_since = Updated_Time(updated_since)

        self._changelog = Changelog(self)

        self._issue_fields: Dict[str, Base_Jira_Field] = {}
        self._search_options: Dict[str, Union[str, List[Prefetcher]]] = {
            'fields': '',
            'prefetchers': []
        }

        self._tables = {
            "issue": Table("issue", filename="data.json"),
            "relationshiptype": Key_Table("relationshiptype", "id")
        }

        self._type_casts = {
            "int": Int_Parser(self),
            "identifier": ID_Parser(self),
            "str": String_Parser(self),
            "boolean": Boolean_Parser(self),
            "date": Date_Parser(self),
            "unicode": Unicode_Parser(self),
            "sprint": Sprint_Parser(self),
            "developer": Developer_Parser(self),
            "decimal": Decimal_Parser(self),
            "id_list": ID_List_Parser(self),
            "version": Version_Parser(self),
            "rank": Rank_Parser(self),
            "issue_key": Issue_Key_Parser(self),
            "flag": Flag_Parser(self),
            "ready_status": Ready_Status_Parser(self),
            "labels": Labels_Parser(self),
            "project": Project_Parser(self),
            "status_category": Status_Category_Parser(self)
        }

        self._import_field_specifications()

    def _make_issue_field(self, name: str, data: Field) \
            -> Optional[Base_Jira_Field]:
        if "property" in data and "field" not in data:
            raise KeyError(f"Field '{name}' must not have property without field name")

        for key, field in self.FIELD_PARSERS:
            if key in data:
                return field(self, name, **data)

        if "special_parser" in data:
            specialization = Special_Field.get_field_class(name)
            return specialization(self, name, **data)

        return None

    def _import_field_specifications(self) -> None:
        # Parse the JIRA field specifications and create field objects,
        # as well as the search fields string.
        jira_fields = []

        with open('jira_fields.json', 'r', encoding='utf-8') as fields_file:
            fields = json.load(fields_file)

        for name, data in fields.items():
            field = self._make_issue_field(name, data)
            if field is not None:
                self._issue_fields[name] = field
                search_field = field.search_field
                if search_field is not None:
                    jira_fields.append(search_field)

                self.register_table(data, table_source=field)

            self._changelog.import_field_specification(name, data, field=field)

        jira_fields.append(self._changelog.search_field)
        self._search_options['fields'] = ','.join(jira_fields)

    def register_table(self, data: Field, table_source: Table_Source) -> None:
        """
        Create a new table storage according to a specification.

        The table can be addressable through a table name which is also used
        by the table for the export filename. The table name is either
        retrieved from a table source or `data`; `data` receives preference.
        `data` must have a "table" key. In case it is a string, then the table
        name is simply that. Otherwise, it is retrieved from the field or other
        source that is registering the table, although a table name from the
        type cast parser has precedence. If none of the sources provide a name,
        The `data` "table" key can also be a dictionary, which is used by some
        table sources for specifying which fields they are going to extract and
        parse. The type cast parser is retrieved from the "type" key of `data`
        if it exists.

        The `table_source` may additionally provide a table key, which can be
        `None`, a string or a tuple, which causes this method to register
        either a normal `Table`, `Key_Table` or `Link_Table`, respectively.
        Note that if the type cast parser has a table key, the table source
        does not define a table key, or no table source is given at all,
        then this check falls back to the type cast parser's table key.

        The reason for this order of preference for name and key, in order
        `data`, type cast, or table source, is the specificity of each source:
        the `data` is meant for exactly one field, the type cast may be used
        by multiple fields, and the table source could be some generic object.
        """

        if "table" not in data:
            return

        table_name: Optional[str] = None
        key = None
        if "type" in data:
            datatype = str(data["type"])
            table_name = self._type_casts[datatype].table_name
            key = self._type_casts[datatype].table_key

        if table_name is None:
            table_name = table_source.table_name
        if key is None:
            key = table_source.table_key

        if isinstance(data["table"], str):
            table_name = data["table"]

        table_options: Dict[str, Any] = {}
        if "table_options" in data and isinstance(data["table_options"], dict):
            table_options = data["table_options"]

        if table_name is None:
            return

        if key is None:
            self._tables[table_name] = Table(table_name, **table_options)
        elif isinstance(key, tuple):
            self._tables[table_name] = Link_Table(table_name, key,
                                                  **table_options)
        else:
            self._tables[table_name] = Key_Table(table_name, key,
                                                 **table_options)

    def register_prefetcher(self, method: Prefetcher) -> None:
        """
        Register a method that is to be called with the `Query` object before
        issues are collected. This allows additional data gathering by fields
        or type cast parsers if they need the data to operate effectively.
        """

        prefetchers = self._search_options['prefetchers']
        if isinstance(prefetchers, list):
            prefetchers.append(method)

    def get_table(self, name: str) -> Table:
        """
        Retrieve a table registered under `name`.
        """

        return self._tables[name]

    def get_type_cast(self, datatype: str) -> Field_Parser:
        """
        Retrieve a type cast parser registered under the key `datatype`.
        """

        return self._type_casts[datatype]

    @property
    def project(self) -> Project:
        """
        Retrieve the Project domain object.
        """

        return self._project

    @property
    def project_key(self) -> str:
        """
        Retrieve the JIRA project key.
        """

        return self._project.jira_key

    @property
    def updated_since(self) -> Updated_Time:
        """
        Retrieve the `Updated_Time` object indicating the last time the data
        was updated.
        """

        return self._updated_since

    @property
    def search_fields(self) -> str:
        """
        Retrieve the comma-separated search fields to be used in the query.
        """

        return str(self._search_options['fields'])

    def search_issues(self, query: Query) -> None:
        """
        Search for issues in batches and extract field data from them.
        """

        had_issues = True
        issues = query.perform_batched_query(had_issues)
        while issues:
            had_issues = False
            for issue in issues:
                had_issues = True
                data = self.collect_fields(issue)
                versions = self._changelog.get_versions(issue, data)
                self._tables["issue"].extend(versions)

            query.update()
            issues = query.perform_batched_query(had_issues)

    def collect_fields(self, issue: Issue) -> Data:
        """
        Extract simple field data from one issue.
        """

        data: Data = {}
        for name, field in self._issue_fields.items():
            result = field.parse(issue)
            if result is not None:
                data[name] = result

        return data

    def write_tables(self) -> None:
        """
        Export all data to separate table-based JSON output files.
        """

        for table in self._tables.values():
            table.write(self._project.export_key)

    def process(self, jira_source: source.Jira, query: Optional[str] = None) -> str:
        """
        Perform all steps to export the issues, fields and additional data
        gathered from a JIRA search. Return the update time of the query.
        """

        query_api = Query(self, jira_source, query)
        if isinstance(self._search_options['prefetchers'], list):
            for prefetcher in self._search_options['prefetchers']:
                prefetcher(query_api)

        self.search_issues(query_api)

        old_source = self.project.sources.find_source_type(source.Jira)
        if old_source:
            self.project.sources.delete(old_source)
        self._add_source(jira_source, query_api.api)

        self.write_tables()
        return query_api.latest_update

    def _add_source(self, jira_source: source.Source, api: JIRA) -> None:
        # Replace the source URL with the one provided by the API if possible
        myself = api.myself()
        regex = api.JIRA_BASE_URL.replace('{', '(?P<').replace('}', '>.*?)')
        match = re.match(regex, str(myself['self']))
        if match:
            try:
                name = api.project(self._project.jira_key).name
            except JIRAError:
                logging.exception('Could not extract name for %s',
                                  self._project.key)
                name = self._project.key

            jira_source = source.Source.from_type('jira',
                                                  name=name,
                                                  url=match.group('server'))
        else:
            logging.warning('Could not extract JIRA base URL from API')

        self.project.sources.add(jira_source)
        self.project.export_sources()
