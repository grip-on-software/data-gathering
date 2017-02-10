"""
Package for classes and utilities related to extracting data from the JIRA API.
"""

import json
import os
from copy import copy
from datetime import datetime
from jira import JIRA

from .field import Jira_Field, Primary_Field, Payload_Field, Property_Field, \
    Changelog_Primary_Field, Changelog_Field
from .parser import Int_Parser, String_Parser, Date_Parser, Unicode_Parser, \
    Sprint_Parser, Developer_Parser, Decimal_Parser, ID_List_Parser, \
    Fix_Version_Parser, Rank_Parser, Issue_Key_Parser, Flag_Parser, \
    Ready_Status_Parser, Labels_Parser
from .special_field import Comment_Field, Issue_Link_Field
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

    Each field has a dictionary of configuration, containing some of:
    - "primary": if given, the property name of the field within the main
      issue's response data.
    - "field": if given, the property name within the "fields" dictionary
      of the issue.
    - "property": if given, the property name within the dictionary
      pointed at by "field".
    - "type": the type of the field value, see Jira.type_casts keys for values.
      This is the type as it will be stored in the issues data, and is
      independent from other data relevant to that field. It is mostly used
      for ensuring we convert to strings correctly. Can have multiple types
      in a tuple, which are applied in order.
    - "changelog_primary"
    - "changelog_name"
    - "table"
    - "special_parser"

    Fields that are retrieved or deduced from only changelog data are those
    without "primary" or "field", i.e., "changelog_id" and "updated_by".
    """

    _special_parser_classes = {
        "comment": Comment_Field,
        "issuelinks": Issue_Link_Field
    }

    def __init__(self, project_key, updated_since):
        self._project_key = project_key
        self._updated_since = Updated_Time(updated_since)

        self._issue_fields = {}
        self._changelog_fields = {}
        self._changelog_primary_fields = {}

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
            "fix_version": Fix_Version_Parser(self),
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

            if "special_parser" in data:
                parser_class = self._special_parser_classes[name]
                parser = parser_class(self, **data)
                self._special_parsers[name] = parser
                self.register_table(data["special_parser"], data,
                                    table_key_source=parser)
                jira_fields.append(name)
            elif "changelog_primary" in data:
                changelog_name = data["changelog_primary"]
                primary_field = Changelog_Primary_Field(self, name, **data)
                self._changelog_primary_fields[changelog_name] = primary_field
            elif "changelog_name" in data:
                changelog_name = data["changelog_name"]
                changelog_field = Changelog_Field(self, name, **data)
                self._changelog_fields[changelog_name] = changelog_field

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

        return self._project_key

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
                versions = self.get_changelog_versions(issue, data)
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

    def fetch_changelog(self, issue):
        """
        Extract fields from the changelog of one issue. The resulting dictionary
        holds the differences of one change and is keyed by the update time,
        but it requires more postprocessing to be used in the output data.
        """

        changelog = issue.changelog.histories
        issue_diffs = {}
        for changes in changelog:
            diffs = {}

            for field in self._changelog_primary_fields.itervalues():
                value = field.parse(changes)
                diffs[field.name] = value

            for item in changes.items:
                changelog_name = str(item.field)
                if changelog_name in self._changelog_fields:
                    field = self._changelog_fields[changelog_name]
                    value = field.parse_changelog(item, diffs)
                    diffs[field.name] = value

            if "updated" not in diffs:
                print "No updated date: " + repr(diffs)
                continue

            updated = diffs["updated"]
            if updated in issue_diffs:
                issue_diffs[updated].update(diffs)
            else:
                issue_diffs[updated] = diffs

        return issue_diffs

    @classmethod
    def _create_change_transition(cls, source_data, diffs):
        """
        Returns a copy of `source_data`, updated with the new key-value pairs
        in `diffs`.
        """

        # Shallow copy
        result = dict(source_data)

        # Count attachments
        if "attachment" in diffs:
            total = int(result["attachment"]) + diffs["attachment"]
            result["attachment"] = str(max(0, total))
            diffs.pop("attachment")

        result.update(diffs)
        return result

    @classmethod
    def _alter_change_metdata(cls, data, diffs):
        data["updated_by"] = diffs.pop("updated_by", str(0))
        data["rank_change"] = diffs.pop("rank_change", str(0))

    def get_changelog_versions(self, issue, data):
        """
        Fetch the versions of the issue based on changelog data as well as
        the current version of the issue.
        """

        issue_diffs = self.fetch_changelog(issue)

        changelog_count = len(issue_diffs)
        prev_diffs = {}
        prev_data = data
        versions = []

        # reestablish issue data from differences
        sorted_diffs = sorted(issue_diffs.keys(), reverse=True)
        for updated in sorted_diffs:
            if not self._updated_since.is_newer(updated):
                break

            diffs = issue_diffs[updated]
            if not prev_diffs:
                data["changelog_id"] = str(changelog_count)
                self._alter_change_metdata(data, diffs)
                versions.append(data)
                prev_diffs = diffs
                changelog_count -= 1
            else:
                prev_diffs["updated"] = updated
                self._alter_change_metdata(prev_diffs, diffs)
                old_data = self._create_change_transition(prev_data, prev_diffs)
                old_data["changelog_id"] = str(changelog_count)
                versions.append(old_data)
                prev_data = old_data
                prev_diffs = diffs
                changelog_count -= 1

        if prev_diffs and self._updated_since.is_newer(data["created"]):
            prev_diffs["updated"] = data["created"]
            new_data = self._create_change_transition(prev_data, prev_diffs)
            new_data["changelog_id"] = str(0)
            versions.append(new_data)

        return versions

    def parse_special_fields(self, issue):
        """
        Parse more complicated fields to let these parsers augment the data.
        """

        for name, parser in self._special_parsers.iteritems():
            if hasattr(issue, name):
                field = getattr(issue, name)
                if field is not None:
                    parser.parse(issue, field)

    def write_tables(self):
        """
        Export all data to separate table-based JSON output files.
        """

        for table in self._tables.itervalues():
            table.write(self._project_key)

    def process(self, username, password, options):
        """
        Perform all steps to export the issues, fields and additional data
        gathered from a JIRA search. Return the update time of the query.
        """

        if not os.path.exists(self._project_key):
            os.mkdir(self._project_key)

        query = Query(self, username, password, options)
        self.search_issues(query)
        self.write_tables()

        return query.latest_update
