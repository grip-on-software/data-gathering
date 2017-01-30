"""
Script to retrieve JIRA issue data and convert it to JSON format readable by
the database importer.
"""

import argparse
import ConfigParser
import json
import os
import re
from abc import ABCMeta, abstractproperty
from datetime import datetime
from jira import JIRA
from utils import parse_date, parse_unicode

###
# Abstract classes
###

class Table_Key_Source(object):
    # pylint: disable=too-few-public-methods

    """
    Abstract mixin class that indicates that subclasses might provide a key for
    use in a `Table` instance.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def table_key(self):
        """
        Key to use for assigning unique rows to a table with parsed values of
        this type, or `None` if there are no keyed tables for this type.
        """

        return None

###
# Type specific parsers
###

class Field_Parser(Table_Key_Source):
    """
    Parser for JIRA fields. Different versions for each type exist.
    """

    def __init__(self, jira):
        self.jira = jira

    def parse(self, value):
        """
        Parse an issue field or changelog value.

        Returns the value formatted according to the type.
        """

        raise NotImplementedError("Must be overridden in subclass")

    def parse_changelog(self, change, value, diffs):
        # pylint: disable=unused-argument,no-self-use
        """
        Parse a changelog row and its parsed value.

        This is only called by changelog fields after the normal parse method.
        Returns the change value the original parsed value if that one should
        be used.
        """

        return value

    @property
    def table_key(self):
        return None

class String_Parser(Field_Parser):
    """
    Parser for string fields.
    """

    def parse(self, value):
        return str(value)

class Int_Parser(String_Parser):
    """
    Parser for integer fields.

    Currently converts the values to strings.
    """

    def parse(self, value):
        return str(int(value))

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields, including date and time.
    """

    def parse(self, value):
        return parse_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    def parse(self, value):
        return parse_unicode(value)

class Sprint_Parser(Field_Parser):
    """
    Parser for sprint representations.
    """

    @classmethod
    def _split_sprint(cls, sprint):
        sprint_data = {}
        sprint_string = str(sprint)
        if '[' not in sprint_string:
            return sprint_data

        sprint_string = sprint_string[sprint_string.rindex('[')+1:-1]
        sprint_parts = sprint_string.split(',')
        for part in sprint_parts:
            try:
                pair = part.split('=')
                key = pair[0].encode('utf-8')
                value = pair[1].encode('utf-8')
                sprint_data[key] = value
            except IndexError:
                return False

        return sprint_data

    def parse(self, sprint):
        sprint_data = self._split_sprint(sprint)
        if not sprint_data:
            return str(0)

        sprint_text = parse_unicode(sprint_data["id"])

        if sprint_data["endDate"] != "<null>" and sprint_data["startDate"] != "<null>":
            self.jira.get_table("sprint").append({
                "id": sprint_text,
                "name": str(sprint_data["name"]),
                "start_date": parse_date(sprint_data["startDate"]),
                "end_date": parse_date(sprint_data["endDate"])
            })

        return sprint_text

    def parse_changelog(self, change, value, diffs):
        if change['from'] is None:
            return str(0)

        return str(int(change['from'].split(', ')[0]))

    @property
    def table_key(self):
        return "id"

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    def parse(self, value):
        return str(float(value))

class Developer_Parser(Field_Parser):
    """
    Parser for fields that contain information about a JIRA user, including
    their account name and usually the display name.
    """

    def parse(self, value):
        if value is not None and hasattr(value, "name"):
            encoded_name = parse_unicode(value.name)
            if value.name is not None and hasattr(value, "displayName"):
                self.jira.get_table("developer").append({
                    "name": encoded_name,
                    "display_name": parse_unicode(value.displayName)
                })

            return encoded_name
        elif isinstance(value, (str, unicode)):
            return parse_unicode(value)
        else:
            return str(0)

    @property
    def table_key(self):
        return "name"

class ID_List_Parser(Field_Parser):
    """
    Parser for fields that contain multiple items that have IDs, such as
    attachments.
    """

    def parse(self, value):
        if not isinstance(value, list):
            # Singular value (changelogs)
            return str(1)

        id_list = [item.id for item in value]
        return str(len(id_list))

    def parse_changelog(self, change, value, diffs):
        change = -1 if value == str(0) else +1
        if "attachment" in diffs:
            value = diffs["attachment"] + change
        else:
            value = change

        return value

class Fix_Version_Parser(Field_Parser):
    """
    Parser for fields that contain the version in which an issue was fixed.
    """

    def parse(self, value):
        if value is None:
            return str(0)

        encoded_value = str(0)

        required_properties = ('id', 'name', 'description', 'released')
        for fix_version in value:
            if all(hasattr(fix_version, prop) for prop in required_properties):
                release_date = str(0)
                if fix_version.released and hasattr(fix_version, 'releaseDate'):
                    release_date = parse_date(fix_version.releaseDate)

                encoded_value = str(fix_version.id)
                self.jira.get_table("fixVersion").append({
                    "id": encoded_value,
                    "name": str(fix_version.name),
                    "description": parse_unicode(fix_version.description),
                    "release_date": release_date
                })

        return encoded_value

    @property
    def table_key(self):
        return "id"

class Rank_Parser(Field_Parser):
    """
    Parser for changelog fields that indicate whether the issue was ranked
    higher or lower on the backlog/storyboard.
    """

    def parse(self, value):
        return str(0)

    def parse_changelog(self, change, value, diffs):
        if change["toString"] == "Ranked higher":
            return str(1)
        if change["toString"] == "Ranked lower":
            return str(-1)

        return value

class Issue_Key_Parser(String_Parser):
    """
    Parser for fields that link to another issue.
    """

    def parse_changelog(self, change, value, diffs):
        if change["fromString"] is not None:
            return change["fromString"]

        return str(0)

class Flag_Parser(Field_Parser):
    """
    Parser for fields that mark the issue when it is set, such as an impediment.
    """

    def parse(self, value):
        if isinstance(value, list):
            if len(value) > 0:
                return str(1)
        elif value != "":
            return str(1)

        return str(0)

class Ready_Status_Parser(Field_Parser):
    """
    Parser for the 'ready status' field, which contains a visual indicator
    of whether the user story can be moved into a refinement or sprint.
    """

    def _add_to_table(self, encoded_id, html):
        match = re.match(r'<font .*><b>(.*)</b></font>', html)
        if match:
            name = match.group(1)
            self.jira.get_table("ready_status").append({
                "id": encoded_id,
                "name": name
            })

    def parse(self, value):
        if value is None:
            return str(0)

        encoded_value = str(0)

        if hasattr(value, 'id') and hasattr(value, 'value'):
            encoded_value = str(value.id)
            self._add_to_table(encoded_value, value.value)

        return encoded_value

    def parse_changelog(self, change, value, diffs):
        if change["from"] is not None:
            value = str(change["from"])
            self._add_to_table(value, change["fromString"])

        return value

    @property
    def table_key(self):
        return "id"

class Labels_Parser(Field_Parser):
    """
    Parser for fields that hold a list of labels.
    """

    def parse(self, value):
        if isinstance(value, list):
            return str(len(value))
        elif isinstance(value, (str, unicode)) and value != "":
            return str(len(value.split(' ')))

        return str(0)

###
# Field definitions
###

class Jira_Field(Table_Key_Source):
    """
    Field parser for the issue field data returned by the JIRA REST API.
    """

    def __init__(self, jira, name, **data):
        self.jira = jira
        self.name = name
        self.data = data

    def fetch(self, issue):
        """
        Retrieve the raw data from the issue.

        This method is responsible for determining the correct field to use, and
        to preprocess it as much as possible (such as extracting an ID from its
        subproperties). The returned value is not yet parsed according to the
        type of the field.
        """

        raise NotImplementedError("Subclasses must extend this method")

    def parse(self, issue):
        """
        Retrieve the field from the issue and parse it so that it receives the
        correct type and format.
        """

        field = self.fetch(issue)
        return self.cast(field)

    def cast(self, field):
        """
        Use the appropriate type cast to convert the fetched field to a string
        representation of the field.
        """

        if field is None:
            return str(0)

        for parser in self.get_types():
            field = parser.parse(field)

        return field

    def get_types(self):
        """
        Retrieve the type parsers that this field uses in sequence to perform
        its type casting actions.
        """

        if "type" in self.data:
            if isinstance(self.data["type"], list):
                types = self.data["type"]
            else:
                types = (self.data["type"],)

            return [self.jira.type_casts[datatype] for datatype in types]

        return []

    @property
    def search_field(self):
        """
        JIRA field name to be added to the search query, or `None` if this
        field is always available within the result.
        """

        raise NotImplementedError("Subclasses must extend this property")

    @property
    def table_key(self):
        raise NotImplementedError("Subclasses must extend this property")

class Primary_Field(Jira_Field):
    """
    A field in the JIRA response that contains primary information of the issue,
    such as the ID or key of the issue.
    """

    def fetch(self, issue):
        return getattr(issue, self.data["primary"])

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Primary field '" + self.name + "' is not keyable at this moment")

class Payload_Field(Jira_Field):
    """
    A field in the JIRA's main payload response, which are the editable fields
    as well as metadata fields for the issue.
    """

    def fetch(self, issue):
        if hasattr(issue.fields, self.data["field"]):
            return getattr(issue.fields, self.data["field"])

        return None

    @property
    def search_field(self):
        return self.data["field"]

    @property
    def table_key(self):
        return "id"

class Property_Field(Payload_Field):
    """
    A field in the JIRA's main payload response of which one property is the
    identifying value for that field in the issue.
    """

    def fetch(self, issue):
        field = super(Property_Field, self).fetch(issue)
        if hasattr(field, self.data["property"]):
            return getattr(field, self.data["property"])

        return None

    def parse(self, issue):
        field = super(Property_Field, self).parse(issue)
        if field is None:
            return None

        if "table" in self.data and isinstance(self.data["table"], dict):
            payload_field = super(Property_Field, self).fetch(issue)
            row = {self.data["property"]: field}
            has_data = False
            for name, datatype in self.data["table"].iteritems():
                if hasattr(payload_field, name):
                    has_data = True
                    prop = getattr(payload_field, name)
                    row[name] = self.jira.type_casts[datatype].parse(prop)
                else:
                    row[name] = str(0)

            if has_data:
                self.jira.get_table(self.name).append(row)

        return field

    @property
    def table_key(self):
        return self.data["property"]

class Changelog_Primary_Field(Jira_Field):
    """
    A field in the change items in the changelog of the JIRA response.
    """

    def fetch(self, issue):
        if hasattr(issue, self.data["changelog_primary"]):
            return getattr(issue, self.data["changelog_primary"])

        return None

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Changelog fields are not keyable at this moment")

class Changelog_Field(Jira_Field):
    """
    A field in the changelog items of the JIRA expanded response.
    """

    def fetch(self, issue):
        data = issue.__dict__
        if data['from'] is not None:
            return data['from']
        if data['fromString'] is not None:
            return data['fromString']

        return None

    def parse_changelog(self, issue, diffs):
        """
        Parse changelog information from a changelog entry.
        """

        field = self.parse(issue)
        for parser in self.get_types():
            field = parser.parse_changelog(issue.__dict__, field, diffs)

        return field

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Changelog fields are not keyable at this moment")

###
# Special field parsers
###

class Special_Field(Table_Key_Source):
    """
    A special field with additional data that cannot be parsed in conventional
    ways and is likely stored in a separate table.
    """

    def __init__(self, jira, **info):
        self.jira = jira
        self.info = info

    def parse(self, issue, field):
        """
        Retrieve relevant data from the field belonging to the issue,
        and store the data where appropriate.
        """

        raise NotImplementedError("Subclasses must override this method")

class Comment_Field(Special_Field):
    """
    Field parser for the comments of a JIRA issue.
    """

    def parse(self, issue, field):
        if hasattr(field, 'comments'):
            for comment in field.comments:
                row = {}
                for subfield, datatype in self.info["table"].iteritems():
                    if subfield in self.info["fields"]:
                        fieldname = self.info["fields"][subfield]
                    else:
                        fieldname = subfield

                    if hasattr(comment, fieldname):
                        prop = getattr(comment, fieldname)
                        row[subfield] = self.jira.type_casts[datatype].parse(prop)
                    else:
                        row[subfield] = str(0)

                    row["issue_id"] = str(issue.id)
                    self.jira.get_table("comment").append(row)

    @property
    def table_key(self):
        return "id"

class Issue_Link_Field(Special_Field):
    """
    Field parser for the issue links related to an issue.
    """

    def parse(self, issue, field):
        for issuelink in field:
            if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                continue

            self.jira.get_table("relationshiptype").append({
                'id': str(issuelink.type.id),
                'name': str(issuelink.type.name),
            })

            if hasattr(issuelink, 'outwardIssue'):
                self.jira.get_table("issuelinks").append({
                    'from_id': str(issue.id),
                    'to_id': str(issuelink.outwardIssue.id),
                    'relationshiptype': str(issuelink.type.id)
                })

            if hasattr(issuelink, 'inwardIssue'):
                self.jira.get_table("issuelinks").append({
                    'from_id': str(issue.id),
                    'to_id': str(issuelink.inwardIssue.id),
                    'relationshiptype': str(issuelink.type.id)
                })

    @property
    def table_key(self):
        return ('from_id', 'to_id', 'relationshiptype')

###
# Table structures
###

class Table(object):
    """
    Data storage for eventual JSON output for the database importer.
    """

    def __init__(self, name, filename=None, **kwargs):
        self.name = name
        self.data = []
        self.options = kwargs

        if filename is None:
            self.filename = 'data_{}.json'.format(self.name)
        else:
            self.filename = filename

    def append(self, row):
        """
        Insert a row into the table.
        Subclasses may check whether the row already exists and ignore it if
        this is the case.
        """

        self.data.append(row)
        return True

    def extend(self, rows):
        """
        Insert multiple rows at once into the table.
        """

        self.data.extend(rows)

    def write(self, folder):
        """
        Export the table data into a file in the given `folder`.
        """

        with open(folder + "/" + self.filename, 'w') as outfile:
            json.dump(self.data, outfile, indent=4)

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name, key, **kwargs):
        super(Key_Table, self).__init__(name, **kwargs)
        self.key = key
        self.keys = set()

    def append(self, row):
        if row[self.key] in self.keys:
            return False

        self.keys.add(row[self.key])
        return super(Key_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)

class Link_Table(Table):
    """
    Data storage for a table that has a combination of columns that make up
    a primary key.
    """

    def __init__(self, name, link_keys, **kwargs):
        super(Link_Table, self).__init__(name, **kwargs)
        self.link_keys = link_keys
        self.links = set()

    def append(self, row):
        # Link values must be hashable
        link_values = tuple(row[key] for key in self.link_keys)
        if link_values in self.links:
            return False

        self.links.add(link_values)
        super(Link_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)

###
# Updated time trackers
###

class Updated_Time(object):
    """
    Tracker for the latest update time from which we query for newly updated
    issues.
    """

    def __init__(self, timestamp):
        self._timestamp = timestamp
        self._date = datetime.strptime(self._timestamp, '%Y-%m-%d %H:%M')

    def is_newer(self, timestamp, timestamp_format='%Y-%m-%d %H:%M:%S'):
        """
        Check whether a given `timestamp`, a string which is formatted according
        to `timestamp_format`, is newer than the update date.
        """

        if self._date < datetime.strptime(timestamp, timestamp_format):
            return True

        return False

    @property
    def timestamp(self):
        """
        Retrieve the timestamp string of the latest update.
        """

        return self._timestamp

    @property
    def date(self):
        """
        Return the datetime object of the latest update.
        """

        return self._date

class Update_Tracker(object):
    """
    Tracker for the update time which controls the storage of this timestamp.
    """

    def __init__(self, project, updated_since=None):
        self.project = project
        self.updated_since = updated_since
        self.filename = self.project + '/jira-updated.txt'

    def get_updated_since(self):
        """
        Retrieve the latest update timestamp from a previous run.
        """

        if self.updated_since is None:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as update_file:
                    self.updated_since = update_file.read().strip()
            else:
                self.updated_since = "0001-01-01 01:01"

        return self.updated_since

    def save_updated_since(self, new_updated_since):
        """
        Store a new latest update time for later reuse.
        """

        with open(self.filename, 'w') as update_file:
            update_file.write(new_updated_since)

###
# Main class
###

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

def validate_date(value):
    """
    Check whether a given value can be correctly parsed as a timestamp with
    a date and time.
    """

    try:
        return Updated_Time(value).timestamp
    except ValueError as error:
        raise argparse.ArgumentTypeError("Not a valid date: " + error.message)

def parse_args():
    """
    Parse command line arguments.
    """

    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")

    description = "Obtain JIRA issue data and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="JIRA project key")
    parser.add_argument("--username", default=config.get("jira", "username"),
                        help="JIRA username")
    parser.add_argument("--password", default=config.get("jira", "password"),
                        help="JIRA password")
    parser.add_argument("--server", default=config.get("jira", "server"),
                        help="JIRA server URL")
    parser.add_argument("--updated-since", default=None, dest="updated_since",
                        type=validate_date,
                        help="Only fetch issues changed since the timestamp (YYYY-MM-DD HH:MM)")
    return parser.parse_args()

def main():
    """
    Main entry point.
    """

    args = parse_args()

    tracker = Update_Tracker(args.project, args.updated_since)
    updated_since = tracker.get_updated_since()

    options = {
        "server": args.server
    }
    jira = Jira(args.project, args.username, args.password, options,
                updated_since)
    jira.process()

    tracker.save_updated_since(jira.get_latest_update())

if __name__ == "__main__":
    main()
