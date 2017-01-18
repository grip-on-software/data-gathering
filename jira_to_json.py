import argparse
import ConfigParser
import json
import os
import re
import traceback
from datetime import datetime
from jira import JIRA
from utils import parse_date, parse_unicode

###
# Type specific parsers
###

class Field_Parser(object):
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
        """
        Parse a changelog row and its parsed value.

        This is only called by changelog fields after the normal parse method.
        Returns the change value the original parsed value if that one should
        be used.
        """

        return value

    @property
    def table_key(self):
        """
        Key to use for assigning unique rows to a table with parsed values of
        this type, or `None` if there are no keyed tables for this type.
        """

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
    def parse(self, value):
        return parse_date(value)

class Unicode_Parser(Field_Parser):
    def parse(self, value):
        return parse_unicode(value)

class Sprint_Parser(Field_Parser):
    def _split_sprint(self, sprint):
        sprint_data = {}
        sprint_string = str(sprint)
        sprint_string = sprint_string[sprint_string.rindex('[')+1:-1]
        sprint_parts = sprint_string.split(',')
        for part in sprint_parts:
            try:
                pair = part.split('=')
                key = pair[0].encode('utf-8')
                value = pair[1].encode('utf-8')
                if key == "endDate" or key == "startDate":
                    value = parse_date(value)

                sprint_data[key] = value
            except IndexError:
                # TODO: Continue or return partial result
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
                "start_date": str(sprint_data["startDate"]),
                "end_date": str(sprint_data["endDate"])
            })

            return sprint_text

        return str(0)

    @property
    def table_key(self):
        return "id"

class Point_Parser(Field_Parser):
    def parse(self, value):
        point_string = str(value)
        head, sep, tail = point_string.partition('.')
        return head

class Developer_Parser(Field_Parser):
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
    def parse(self, value):
        if value is None:
            return str(0)

        encoded_value = str(0)

        for fixVersion in value:
            if hasattr(fixVersion, 'id') and hasattr(fixVersion, 'name') and hasattr(fixVersion, 'description') and hasattr(fixVersion, 'released'):
                release_date = str(0)
                if fixVersion.released and hasattr(fixVersion, 'releaseDate'):
                    release_date = parse_date(fixVersion.releaseDate)

                encoded_value = str(fixVersion.id)
                self.jira.get_table("fixVersion").append({
                    "id": encoded_value,
                    "name": str(fixVersion.name),
                    "description": parse_unicode(fixVersion.description),
                    "release_date": release_date
                })

        return encoded_value

    @property
    def table_key(self):
        return "id"

class Rank_Parser(Field_Parser):
    def parse(self, value):
        return str(0)

    def parse_changelog(self, change, value, diffs):
        # TODO: Only toString is available
        if change["toString"] == "Ranked higher":
            return str(1)
        if change["toString"] == "Ranked lower":
            return str(-1)

        return value

class Issue_Key_Parser(String_Parser):
    def parse_changelog(self, change, value, diffs):
        if change["fromString"] is not None:
            return change["fromString"]

        return str(0)

class Flag_Parser(Field_Parser):
    def parse(self, value):
        if isinstance(value, list):
            if len(value) > 0:
                return str(1)
        elif value != "":
            return str(1)

        return str(0)

class Ready_Status_Parser(Field_Parser):
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

###
# Field definitions
###

class Jira_Field(object):
    """
    Field parser for the issue field data returned by the JIRA REST API.
    """

    def __init__(self, jira, name, **data):
        self.jira = jira
        self.name = name
        self.data = data

    def fetch(self, issue):
        raise NotImplementedError("Subclasses must extend this method")

    def parse(self, issue):
        field = self.fetch(issue)
        return self.cast(field)

    def cast(self, field):
        if field is None:
            return str(0)

        for parser in self.get_types():
            field = parser.parse(field)

        return field

    def get_types(self):
        if "type" in self.data:
            if isinstance(self.data["type"], list):
                types = self.data["type"]
            else:
                types = (self.data["type"],)

            return [self.jira.type_casts[datatype] for datatype in types]

        return []

    @property
    def search_field(self):
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
                    #print("missing data for {}, prop {}".format(self.name, name))
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

class Table(object):
    """
    Data storage for eventual JSON output for the database importer.
    """

    def __init__(self, name):
        self.name = name
        self.data = []

    def append(self, row):
        self.data.append(row)
        return True

    def extend(self, rows):
        self.data.extend(rows)

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name, key):
        super(Key_Table, self).__init__(name)
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

    def __init__(self, name, link_keys):
        super(Link_Table, self).__init__(name)
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
    def __init__(self, timestamp):
        self.timestamp = timestamp
        self.date = datetime.strptime(self.timestamp, '%Y-%m-%d %H:%M')

    def is_newer(self, timestamp, timestamp_format='%Y-%m-%d %H:%M:%S'):
        if self.date < datetime.strptime(timestamp, timestamp_format):
            return True

        return False

class Update_Tracker(object):
    def __init__(self, project, updated_since=None):
        self.project = project
        self.updated_since = updated_since
        self.filename = self.project + '/jira-updated.txt'

    def get_updated_since(self):
        if self.updated_since is None:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.updated_since = f.read().strip()
            else:
                self.updated_since = "0001-01-01 01:01"

        return self.updated_since

    def save_updated_since(self, new_updated_since):
        with open(self.filename, 'w') as f:
            f.write(new_updated_since)

###
# Main class
###

class Jira(object):
    """
    JIRA parser and extraction tool.
    """

    """
    Fields extracted from JIRA.

    Each field has a dictionary of configuration, containing some of:
    - "primary": if given, the property name of the field within the main
      issue's response data.
    - "field": if given, the property name within the "fields" dictionary
      of the issue.
    - "property": if given, the property name within the dictionary 
      pointed at by "field".
    - "type": the type of the field value, can be "str", "int", "date",
      "unicode", "point", "sprint", "name" or "id_list".
      This is the type as it will be stored in the issues data, and is
      independent from other data relevant to that field. It is mostly used
      for ensuring we convert to strings correctly. Can have multiple types
      in a tuple, which are applied in order.
    - "changelog_primary"
    - "changelog_name"
    - "table"

    Fields that are retrieved or deduced from only changelog data are those
    without "primary" or "field", i.e., "changelog_id" and "updated_by".
    """

    def __init__(self, project_key, username, password, options, updated_since):
        self.jira_project_key = project_key
        self.jira_username = username
        self.jira_password = password
        self.jira_api = JIRA(options,
            basic_auth=(self.jira_username, self.jira_password)
        )
        self.updated_since = Updated_Time(updated_since)
        self.latest_update = str(0)

        self.query = 'project={} AND updated > "{}"'.format(self.jira_project_key, self.updated_since.timestamp)

        self.data_folder = self.jira_project_key

        self.issue_fields = {}
        self.changelog_fields = {}
        self.changelog_primary_fields = {}

        self.extra_data_parsers = {
            "comment": self.parse_comments,
            "issuelinks": self.parse_issuelinks
        }

        self.tables = {
            "issue": Table("issue"),
            "relationshiptype": Key_Table("relationshiptype", "id"),
            "comments": Table("comments"),
            "issueLinks": Link_Table("issuelinks",
                ("from_id", "to_id", "relationshiptype")
            ),
            "ready_status": Key_Table("ready_status", "id")
        }

        self.type_casts = {
            "int": Int_Parser(self),
            "str": String_Parser(self),
            "date": Date_Parser(self),
            "unicode": Unicode_Parser(self),
            "sprint": Sprint_Parser(self),
            "developer": Developer_Parser(self),
            "point": Point_Parser(self),
            "id_list": ID_List_Parser(self),
            "fix_version": Fix_Version_Parser(self),
            "rank": Rank_Parser(self),
            "issue_key": Issue_Key_Parser(self),
            "flag": Flag_Parser(self),
            "ready_status": Ready_Status_Parser(self)
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
        # Parse the JIRA field specifications and create field objects as well 
        # as the search fields string.
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

                if "table" in data:
                    if isinstance(data["table"], dict):
                        table_name = name
                    else:
                        table_name = data["table"]

                    key = None
                    if "type" in data:
                        datatype = data["type"]
                        key = self.type_casts[datatype].table_key

                    if key is None:
                        key = self.issue_fields[name].table_key

                    self.tables[table_name] = Key_Table(table_name, key)

            if "changelog_primary" in data:
                changelog_name = data["changelog_primary"]
                field = Changelog_Primary_Field(self, name, **data)
                self.changelog_primary_fields[changelog_name] = field
            elif "changelog_name" in data:
                changelog_name = data["changelog_name"]
                field = Changelog_Field(self, name, **data)
                self.changelog_fields[changelog_name] = field

        jira_fields.extend(self.extra_data_parsers.keys())

        self.jira_search_fields = ','.join(jira_fields)

    def get_table(self, name):
        return self.tables[name]

    def _perform_batched_query(self, start_at, iterate_size):
        self.latest_update = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M")
        return self.jira_api.search_issues(self.query,
            startAt=start_at,
            maxResults=iterate_size,
            expand='attachment,changelog',
            fields=self.jira_search_fields
        )

    def search_issues(self):
        start_at = 0
        iterate_size = 100
        iterate_max = 100000

        issues = self._perform_batched_query(start_at, iterate_size)
        while issues and iterate_size <= iterate_max:
            for issue in issues:
                data = self.collect_fields(issue)
                versions = self.get_changelog_versions(issue, data)
                self.tables["issue"].extend(versions)

                for parse in self.extra_data_parsers.itervalues():
                    parse(issue)

            start_at = start_at + iterate_size
            if start_at + iterate_size > iterate_max:
                iterate_size = iterate_max - start_at

            issues = self._perform_batched_query(start_at, iterate_size)

    def collect_fields(self, issue):
        data = {}
        for name, field in self.issue_fields.iteritems():
            try:
                data[name] = field.parse(issue)
            except:
                print("Error trying to parse field '" + name + "', issue: " + repr(issue) + " fields: " + repr(issue.fields.__dict__))
                raise

        return data

    def fetch_changelog(self, issue):
        changelog = issue.changelog.histories
        issue_diffs = {}
        for changes in changelog:
            diffs = {}

            for name, field in self.changelog_primary_fields.iteritems():
                value = field.parse(changes)
                diffs[field.name] = value

            for item in changes.items:
                changelog_name = str(item.field)
                if changelog_name in self.changelog_fields:
                    field = self.changelog_fields[changelog_name]
                    value = field.parse_changelog(item, diffs)
                    diffs[field.name] = value

            if "updated" not in diffs:
                print("No updated date: " + repr(diffs))
                continue

            updated = diffs["updated"]
            if updated in issue_diffs:
                issue_diffs[updated].update(diffs)
            else:
                issue_diffs[updated] = diffs

        return issue_diffs

    def _create_change_transition(self, source_data, diffs):
        """
        Returns a copy of `source_data`, updated with the new key-value pairs
        in `diffs`.
        """

        # Shallow copy
        result = dict(source_data)

        # Count attachments
        if "attachment" in diffs:
            result["attachment"] = str(max(0,
                int(result["attachment"]) + diffs["attachment"]
            ))

            diffs.pop("attachment")

        result.update(diffs)
        return result

    def _alter_change_metdata(self, data, diffs):
        data["updated_by"] = diffs.pop("updated_by", str(0))
        data["rank_change"] = diffs.pop("rank_change", str(0))

    def get_changelog_versions(self, issue, data):
        issue_diffs = self.fetch_changelog(issue)

        changelog_count = len(issue_diffs)
        prev_diffs = {}
        prev_data = data
        versions = []

        # reestablish issue data from differences
        for updated in sorted(issue_diffs.keys(), reverse=True):
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

    def parse_comments(self, issue):
        if hasattr(issue.fields, 'comment') and issue.fields.comment is not None:
            if hasattr(issue.fields.comment, 'comments'):
                for comment in issue.fields.comment.comments:
                    if hasattr(comment, 'body') and hasattr(comment, 'author') and hasattr(comment, 'id') and hasattr(comment, 'created'):
                        self.tables["comments"].append({
                            'id': str(comment.id),
                            'issue_id': str(issue.id),
                            'author': parse_unicode(comment.author.name),
                            'comment': parse_unicode(comment.body),
                            'created_at': parse_date(comment.created)
                        })

    def parse_issuelinks(self, issue):
        if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks is not None:
            for issuelink in issue.fields.issuelinks:
                if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                    continue

                self.tables["relationshiptype"].append({
                    'id': str(issuelink.type.id), 
                    'name': str(issuelink.type.name),
                })

                if hasattr(issuelink, 'outwardIssue'):
                    self.tables["issueLinks"].append({
                        'from_id': str(issue.id),
                        'to_id': str(issuelink.outwardIssue.id),
                        'relationshiptype': issuelink.type.id
                    })

                if hasattr(issuelink, 'inwardIssue'):
                    self.tables["issueLinks"].append({
                        'from_id': str(issue.id),
                        'to_id': str(issuelink.inwardIssue.id),
                        'relationshiptype': issuelink.type.id
                    })

    def write_tables(self):
        for table in self.tables.itervalues():
            self.write_table(table)

    def write_table(self, table):
        if table.name == "issue":
            filename = "data.json"
        else:
            filename = "data_" + table.name + ".json"

        with open(self.data_folder + "/" + filename, 'w') as outfile:
            json.dump(table.data, outfile, indent=4)

    def process(self):
        if not os.path.exists(self.data_folder):
            os.mkdir(self.data_folder)

        self.search_issues()
        self.write_tables()

    def get_latest_update(self):
        return self.latest_update

def validate_date(value):
    try:
        return Updated_Time(value).timestamp
    except ValueError as e:
        raise argparse.ArgumentTypeError("Not a valid date: " + e.message)

def parse_args():
    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")

    parser = argparse.ArgumentParser(description="Obtain JIRA issue information and convert it to JSON format readable by the database importer.")
    parser.add_argument("project", help="JIRA project key")
    parser.add_argument("--username", default=config.get("jira", "username"), help="JIRA username")
    parser.add_argument("--password", default=config.get("jira", "password"), help="JIRA password")
    parser.add_argument("--server", default=config.get("jira", "server"), help="JIRA server URL")
    parser.add_argument("--updated-since", default=None, dest="updated_since", type=validate_date, help="Only fetch issues that were changed since the given timestamp (YYYY-MM-DD HH:MM)")
    return parser.parse_args()

def main():
    args = parse_args()

    tracker = Update_Tracker(args.project, args.updated_since)
    updated_since = tracker.get_updated_since()

    options = {
        "server": args.server
    }
    jira = Jira(args.project, args.username, args.password, options,
        updated_since
    )
    jira.process()

    tracker.save_updated_since(jira.get_latest_update())

if __name__ == "__main__":
    main()
