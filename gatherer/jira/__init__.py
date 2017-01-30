"""
Package for classes and utilities related to extracting data from the JIRA API.
"""

#import .parser
import json
import os
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

__all__ = ["Jira"]

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

    def __init__(self, project_key, username, password, options, updated_since):
        self.project_key = project_key
        self.jira_api = JIRA(options, basic_auth=(username, password))
        self.updated_since = Updated_Time(updated_since)
        self.latest_update = str(0)

        query = 'project={} AND updated > "{}"'
        self.query = query.format(self.project_key,
                                  self.updated_since.timestamp)

        self.issue_fields = {}
        self.changelog_fields = {}
        self.changelog_primary_fields = {}

        self.special_parser_classes = {
            "comment": Comment_Field,
            "issuelinks": Issue_Link_Field
        }
        self.special_parsers = {}

        self.tables = {
            "issue": Table("issue", filename="data.json"),
            "relationshiptype": Key_Table("relationshiptype", "id")
        }

        self.type_casts = {
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
                self.issue_fields[name] = field
                search_field = self.issue_fields[name].search_field
                if search_field is not None:
                    jira_fields.append(search_field)

                self.register_table(name, data, table_key_source=field)

            if "special_parser" in data:
                parser_class = self.special_parser_classes[name]
                parser = parser_class(self, **data)
                self.special_parsers[name] = parser
                self.register_table(data["special_parser"], data,
                                    table_key_source=parser)
                jira_fields.append(name)
            elif "changelog_primary" in data:
                changelog_name = data["changelog_primary"]
                primary_field = Changelog_Primary_Field(self, name, **data)
                self.changelog_primary_fields[changelog_name] = primary_field
            elif "changelog_name" in data:
                changelog_name = data["changelog_name"]
                changelog_field = Changelog_Field(self, name, **data)
                self.changelog_fields[changelog_name] = changelog_field

        self.jira_search_fields = ','.join(jira_fields)

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
                key = self.type_casts[datatype].table_key

            if key is None and table_key_source is not None:
                key = table_key_source.table_key

            if key is None:
                self.tables[table_name] = Table(table_name)
            elif isinstance(key, tuple):
                self.tables[table_name] = Link_Table(table_name, key)
            else:
                self.tables[table_name] = Key_Table(table_name, key)

    def get_table(self, name):
        """
        Retrieve a table registered under `name`.
        """

        return self.tables[name]

    def _perform_batched_query(self, start_at, iterate_size):
        self.latest_update = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M")
        return self.jira_api.search_issues(self.query,
                                           startAt=start_at,
                                           maxResults=iterate_size,
                                           expand='attachment,changelog',
                                           fields=self.jira_search_fields)

    def search_issues(self):
        """
        Search for issues in batches and extract field data from them.
        """

        start_at = 0
        iterate_size = 100
        iterate_max = 100000

        issues = self._perform_batched_query(start_at, iterate_size)
        while issues and iterate_size <= iterate_max:
            for issue in issues:
                data = self.collect_fields(issue)
                versions = self.get_changelog_versions(issue, data)
                self.tables["issue"].extend(versions)

                self.parse_special_fields(issue)

            start_at = start_at + iterate_size
            if start_at + iterate_size > iterate_max:
                iterate_size = iterate_max - start_at

            issues = self._perform_batched_query(start_at, iterate_size)

    def collect_fields(self, issue):
        """
        Extract simple field data from one issue.
        """

        data = {}
        for name, field in self.issue_fields.iteritems():
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

            for field in self.changelog_primary_fields.itervalues():
                value = field.parse(changes)
                diffs[field.name] = value

            for item in changes.items:
                changelog_name = str(item.field)
                if changelog_name in self.changelog_fields:
                    field = self.changelog_fields[changelog_name]
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
            if not self.updated_since.is_newer(updated):
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

        if prev_diffs and self.updated_since.is_newer(data["created"]):
            prev_diffs["updated"] = data["created"]
            new_data = self._create_change_transition(prev_data, prev_diffs)
            new_data["changelog_id"] = str(0)
            versions.append(new_data)

        return versions

    def parse_special_fields(self, issue):
        """
        Parse more complicated fields to let these parsers augment the data.
        """

        for name, parser in self.special_parsers.iteritems():
            if hasattr(issue, name):
                field = getattr(issue, name)
                if field is not None:
                    parser.parse(issue, field)

    def write_tables(self):
        """
        Export all data to separate table-based JSON output files.
        """

        for table in self.tables.itervalues():
            table.write(self.project_key)

    def process(self):
        """
        Perform all steps to export the issues, fields and additional data
        gathered from a JIRA search.
        """

        if not os.path.exists(self.project_key):
            os.mkdir(self.project_key)

        self.search_issues()
        self.write_tables()

    def get_latest_update(self):
        """
        Return the time of the latest query update.
        """

        return self.latest_update
