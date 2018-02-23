"""
Type specific parsers that convert field values to correct format.
"""

from past.builtins import basestring
from builtins import str
import logging
import re
import jira.resources as resources
from .base import Table_Source
from ..utils import parse_date, parse_unicode

class StatusCategory(resources.Resource):
    """
    Specialized resource for status category field.
    """

    def __init__(self, options, session, raw=None):
        super(StatusCategory, self).__init__('statuscategory/{0}', options, session)
        if raw:
            self._parse_raw(raw)

resources.resource_class_map[r'statuscategory/[^/]+$'] = StatusCategory

class Field_Parser(Table_Source):
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
        Parse a changelog item and its parsed value.

        This is only called by changelog fields after the normal parse method.
        Returns the change value the original parsed value if that one should
        be used.
        """

        return value

    @property
    def table_name(self):
        return None

    @property
    def table_key(self):
        return None

class String_Parser(Field_Parser):
    """
    Parser for string fields.
    """

    def parse(self, value):
        if value is None:
            return None

        return str(value)

class Int_Parser(String_Parser):
    """
    Parser for integer fields.

    Currently converts the values to strings.
    """

    def parse(self, value):
        if value is None:
            return str(0)

        if isinstance(value, basestring) and '.' in value:
            logging.info('Decimal point in integer value: %s', value)
            value = value.split('.', 1)[0]

        return str(int(value))

class ID_Parser(Field_Parser):
    """
    Parser for identifier fields which may be missing.
    """

    def parse(self, value):
        if value is None:
            return None

        return str(int(value))

class Boolean_Parser(String_Parser):
    """
    Parser for string fields that only have two options: "Yes" or "No".
    """

    def parse(self, value):
        if value == "Yes":
            return str(1)
        if value == "No":
            return str(-1)
        if value is None or value == "":
            return None

        return value

    def parse_changelog(self, change, value, diffs):
        return self.parse(change["fromString"])

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields, including date and time.
    """

    def parse(self, value):
        if value is None:
            return None

        return parse_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    def parse(self, value):
        if value is None:
            return None

        return parse_unicode(value)

class Sprint_Parser(Field_Parser):
    """
    Parser for sprint representations.

    This adds sprint data such as start and end dates to a table, and returns
    a list of sprint IDs as the field value. Note that the sprint IDs need to
    be post-processed in order to export it in a way that the importer can
    handle them. Another issue (version) handler need to compare which sprint
    ID is correct for this issue version.
    """

    @classmethod
    def _split_sprint(cls, sprint):
        sprint_data = {}
        sprint_string = parse_unicode(sprint)
        if '[' not in sprint_string:
            return sprint_data

        sprint_string = sprint_string[sprint_string.rindex('[')+1:-1]
        sprint_parts = sprint_string.split(',')
        for part in sprint_parts:
            try:
                pair = part.split('=')
                key = pair[0]
                value = pair[1]
                sprint_data[key] = value
            except IndexError:
                return False

        return sprint_data

    def parse(self, value):
        if value is None:
            return None

        if isinstance(value, list):
            sprints = []
            for sprint_field in value:
                sprint_id = self._parse(sprint_field)
                if sprint_id is not None:
                    sprints.append(sprint_id)

            if not sprints:
                return None

            return sprints

        return self._parse(value)

    def _parse(self, sprint):
        # Parse an individual sprint, add its data to the table and return the
        # sprint ID as an integer, or `None` if it is not an acceptable
        # sprint format.
        sprint_data = self._split_sprint(sprint)
        if not sprint_data:
            return None

        sprint_id = int(sprint_data["id"])

        if sprint_data["endDate"] != "<null>" and sprint_data["startDate"] != "<null>":
            row = {
                "id": str(sprint_id),
                "name": str(sprint_data["name"]),
                "start_date": parse_date(sprint_data["startDate"]),
                "end_date": parse_date(sprint_data["endDate"]),
            }
            if sprint_data["completeDate"] != "<null>":
                row["complete_date"] = parse_date(sprint_data["completeDate"])

            if "goal" in sprint_data and sprint_data["goal"] != "<null>":
                row["goal"] = parse_unicode(sprint_data["goal"])

            self.jira.get_table("sprint").append(row)

        return sprint_id

    def parse_changelog(self, change, value, diffs):
        if change['from'] is None:
            return None

        return [int(sprint) for sprint in change['from'].split(', ')]

    @property
    def table_name(self):
        return "sprint"

    @property
    def table_key(self):
        return "id"

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    def parse(self, value):
        if value is None:
            return None

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
                    "display_name": parse_unicode(value.displayName),
                    "email": parse_unicode(value.emailAddress)
                })

            return encoded_name
        elif isinstance(value, str):
            return parse_unicode(value)
        else:
            return None

    @property
    def table_name(self):
        return "developer"

    @property
    def table_key(self):
        return "name"

class Status_Category_Parser(Field_Parser):
    """
    Parser for subfields containing the status category.
    """

    def __init__(self, jira):
        super(Status_Category_Parser, self).__init__(jira)
        self.jira.register_table({
            "table": {
                "id": "int",
                "key": "str",
                "name": "unicode",
                "color": "unicode"
            }
        }, table_source=self)

    def parse(self, value):
        if value is not None:
            self.jira.get_table("status_category").append({
                "id": value.id,
                "key": str(value.key),
                "name": parse_unicode(value.name),
                "color": parse_unicode(value.colorName)
            })
            return value.id

        return None

    @property
    def table_name(self):
        return "status_category"

    @property
    def table_key(self):
        return "id"

class ID_List_Parser(Field_Parser):
    """
    Parser for fields that contain multiple items that have IDs, such as
    attachments.
    """

    def parse(self, value):
        # Determine the number of items in the list.
        if value is None:
            return str(0)

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

class Version_Parser(Field_Parser):
    """
    Parser for fields that contain the version in which an issue was fixed or
    which is affected by the issue.
    """

    def __init__(self, jira):
        super(Version_Parser, self).__init__(jira)
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query):
        """
        Retrieve data about all fix version releases for the project registered
        in Jira using the query API, and store the data in a table.
        """

        versions = query.api.project_versions(self.jira.project_key)
        self.parse(versions)

    def parse(self, value):
        if value is None:
            return None
        if not isinstance(value, list):
            return str(value)

        encoded_value = None

        required_properties = ('id', 'name', 'description', 'released')
        for fix_version in value:
            if all(hasattr(fix_version, prop) for prop in required_properties):
                start_date = str(0)
                release_date = str(0)
                released = str(-1)
                if fix_version.released:
                    released = str(1)
                if hasattr(fix_version, 'startDate'):
                    start_date = parse_date(fix_version.startDate)
                if hasattr(fix_version, 'releaseDate'):
                    release_date = parse_date(fix_version.releaseDate)

                encoded_value = str(fix_version.id)
                self.jira.get_table("fixVersion").append({
                    "id": encoded_value,
                    "name": str(fix_version.name),
                    "description": parse_unicode(fix_version.description),
                    "start_date": start_date,
                    "release_date": release_date,
                    "released": released
                })

        return encoded_value

    @property
    def table_name(self):
        return "fixVersion"

    @property
    def table_key(self):
        return "id"

class Rank_Parser(Field_Parser):
    """
    Parser for changelog fields that indicate whether the issue was ranked
    higher or lower on the backlog/storyboard.
    """

    def parse(self, value):
        return None

    def parse_changelog(self, change, value, diffs):
        # Encode the rank change as "-1" or "1".
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

        return None

class Flag_Parser(Field_Parser):
    """
    Parser for fields that mark the issue when it is set, such as an impediment.
    """

    def parse(self, value):
        # Output the flagged state as either "0" or "1".
        if (isinstance(value, list) and value) or value != "":
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
            return None

        encoded_value = None

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
    def table_name(self):
        return "ready_status"

    @property
    def table_key(self):
        return "id"

class Labels_Parser(Field_Parser):
    """
    Parser for fields that hold a list of labels.
    """

    def parse(self, value):
        # Count the number of labels.
        if isinstance(value, list):
            return str(len(value))
        elif isinstance(value, str) and value != "":
            return str(len(value.split(' ')))

        return str(0)

class Project_Parser(Field_Parser):
    """
    Parser for fields that hold a project.
    """

    def __init__(self, jira):
        super(Project_Parser, self).__init__(jira)

        self._projects = {}
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query):
        """
        Retrieve data about all projects known to us and keep a id-to-name
        mapping.
        """

        for project in query.api.projects():
            self.parse(project)

    def parse(self, value):
        if value is None:
            return None

        if hasattr(value, 'id') and hasattr(value, 'key'):
            encoded_key = str(value.key)
            self._projects[str(value.id)] = encoded_key

            # Default value for the project is the own project.
            # For external project, ignore the field if it is set to itself.
            if encoded_key == self.jira.project.jira_key:
                return None

            return encoded_key

        return None

    def parse_changelog(self, change, value, diffs):
        if change["from"] is not None:
            project_id = str(change["from"])
            if project_id in self._projects:
                return self._projects[project_id]

            logging.info('Unknown old external project ID %s', project_id)

        return value
