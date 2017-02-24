"""
Type specific parsers that convert field values to correct format.
"""

import re
from .base import Table_Key_Source
from ..utils import parse_date, parse_unicode

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

    def parse(self, sprint):
        if isinstance(sprint, list):
            latest_sprint = str(0)
            for sprint_field in sprint:
                sprint_id = self._parse(sprint_field)
                if sprint_id != str(0):
                    latest_sprint = sprint_id

            return latest_sprint
        else:
            return self._parse(sprint)

    def _parse(self, sprint):
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

class Version_Parser(Field_Parser):
    """
    Parser for fields that contain the version in which an issue was fixed or
    which is affected by the issue.
    """

    def parse(self, value):
        if value is None:
            return str(0)
        if not isinstance(value, list):
            return str(value)

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