"""
Package for classes and utilities related to extracting data from the JIRA API.
"""

import json
import os
from copy import copy
from datetime import datetime
from jira import JIRA

from .changelog import Changelog
from .field import Jira_Field, Primary_Field, Payload_Field, Property_Field
from .parser import Int_Parser, String_Parser, Date_Parser, Unicode_Parser, \
    Sprint_Parser, Developer_Parser, Decimal_Parser, ID_List_Parser, \
    Version_Parser, Rank_Parser, Issue_Key_Parser, Flag_Parser, \
    Ready_Status_Parser, Labels_Parser
from .special_field import Comment_Field, Issue_Link_Field, Subtask_Field
from .table import Table, Key_Table, Link_Table
from .update import Updated_Time, Update_Tracker
from ..utils import Iterator_Limiter

__all__ = ["Jira"]

class Query(object):
    """
    Object that handles the JIRA API query using limiting.
    """

    def __init__(self, jira, username, password, options):
        self._jira = jira
        self._api = JIRA(options, basic_auth=(username, password))

        query = 'project={} AND updated > "{}"'
        self._query = query.format(self._jira.project_key,
                                   self._jira.updated_since.timestamp)
        self._search_fields = self._jira.search_fields
        self._latest_update = str(0)

        self._iterator_limiter = Iterator_Limiter(size=100, maximum=100000)

    def update(self):
        """
        Update the internal iteration tracker after processing a query.
        """

        self._iterator_limiter.update()

    def perform_batched_query(self, had_issues):
        """
        Retrieve a batch of issue results from the JIRA API.
        """

        if not self._iterator_limiter.check(had_issues):
            return []

        self._latest_update = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M")
        return self._api.search_issues(self._query,
                                       startAt=self._iterator_limiter.skip,
                                       maxResults=self._iterator_limiter.size,
                                       expand='attachment,changelog',
                                       fields=self._search_fields)

    @property
    def latest_update(self):
        """
        Retrieve the latest time that the query retrieved data.
        """

        return self._latest_update

class Jira(object):
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

    _special_parser_classes = {
        "comment": Comment_Field,
        "issuelinks": Issue_Link_Field,
        "subtasks": Subtask_Field
    }

    def __init__(self, project, updated_since):
        self._project = project
        self._updated_since = Updated_Time(updated_since)

        self._changelog = Changelog(self)

        self._issue_fields = {}
        self._special_parsers = {}

        self._tables = {
            "issue": Table("issue", filename="data.json"),
            "relationshiptype": Key_Table("relationshiptype", "id")
        }

        self._type_casts = {
            "int": Int_Parser(self),
            "str": String_Parser(self),
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
            "labels": Labels_Parser(self)
        }

        self._import_field_specifications()

    def _make_issue_field(self, name, data):
        if "primary" in data:
            return Primary_Field(self, name, **data)
        elif "field" in data:
            if "property" in data:
                return Property_Field(self, name, **data)
            else:
                return Payload_Field(self, name, **data)

        return None

    def _import_field_specifications(self):
        # Parse the JIRA field specifications and create field objects,
        # as well as the search fields string.
        jira_fields = []

        with open("jira_fields.json", "r") as fields_file:
            fields = json.load(fields_file)

        for name, data in fields.iteritems():
            field = self._make_issue_field(name, data)
            if field is not None:
                self._issue_fields[name] = field
                search_field = self._issue_fields[name].search_field
                if search_field is not None:
                    jira_fields.append(search_field)

                self.register_table(name, data, table_key_source=field)
            elif "special_parser" in data:
                parser_class = self._special_parser_classes[name]
                parser = parser_class(self, **data)
                self._special_parsers[name] = parser
                self.register_table(data["special_parser"], data,
                                    table_key_source=parser)
                jira_fields.append(name)

            self._changelog.import_field_specification(name, data)

        jira_fields.append(self._changelog.search_field)
        self._search_fields = ','.join(jira_fields)

    def register_table(self, name, data, table_key_source=None):
        """
        Create a new table storage according to a specification.

        The table can be addressable through either `name` or `data`, which is
        also used by the table for filenames; `data` receives preference.
        In that case where `data` is a string, then `name` is simply the name
        of the field or other source that is registering the table.
        The `data` can also be a dictionary, which is used by some table sources
        for specifying which fields they are going to extract and parse.
        The `table_key_source` provides a table key, which can be `None`,
        a string or a tuple, which leads to a normal `Table`, `Key_Table` or
        `Link_Table` respectively.
        """

        if "table" in data:
            if isinstance(data["table"], dict):
                table_name = name
            else:
                table_name = data["table"]

            key = None
            if "type" in data:
                datatype = data["type"]
                key = self._type_casts[datatype].table_key

            if key is None and table_key_source is not None:
                key = table_key_source.table_key

            if key is None:
                self._tables[table_name] = Table(table_name)
            elif isinstance(key, tuple):
                self._tables[table_name] = Link_Table(table_name, key)
            else:
                self._tables[table_name] = Key_Table(table_name, key)

    def get_table(self, name):
        """
        Retrieve a table registered under `name`.
        """

        return self._tables[name]

    def get_type_cast(self, datatype):
        """
        Retrieve a type cast parser registered under the key `datatype`.
        """

        return self._type_casts[datatype]

    @property
    def project_key(self):
        """
        Retrieve the JIRA project key.
        """

        return self._project.jira_key

    @property
    def updated_since(self):
        """
        Retrieve the `Updated_Time` object indicating the last time the data
        was updated.
        """

        return self._updated_since

    @property
    def search_fields(self):
        """
        Retrieve the list of search fields to be used in the query.
        """

        return copy(self._search_fields)

    def search_issues(self, query):
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

                self.parse_special_fields(issue)

            query.update()
            issues = query.perform_batched_query(had_issues)

    def collect_fields(self, issue):
        """
        Extract simple field data from one issue.
        """

        data = {}
        for name, field in self._issue_fields.iteritems():
            data[name] = field.parse(issue)

        return data

    def parse_special_fields(self, issue):
        """
        Parse more complicated fields to let these parsers augment the data.
        """

        for name, parser in self._special_parsers.iteritems():
            if hasattr(issue.fields, name):
                field = getattr(issue.fields, name)
                if field is not None:
                    parser.parse(issue, field)

    def write_tables(self):
        """
        Export all data to separate table-based JSON output files.
        """

        for table in self._tables.itervalues():
            table.write(self._project.export_key)

    def process(self, username, password, options):
        """
        Perform all steps to export the issues, fields and additional data
        gathered from a JIRA search. Return the update time of the query.
        """

        query = Query(self, username, password, options)
        self.search_issues(query)
        self.write_tables()

        return query.latest_update
