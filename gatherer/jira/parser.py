"""
Type specific parsers that convert field values to correct format.
"""

import logging
import re
from typing import Any, Dict, Mapping, Optional, TYPE_CHECKING
from .base import Table_Source, TableKey
from .query import Query
from ..utils import parse_date, parse_unicode
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira
else:
    Jira = object

class Field_Parser(Table_Source):
    """
    Parser for JIRA fields. Different versions for each type exist.
    """

    def __init__(self, jira: Jira) -> None:
        self.jira = jira

    def parse(self, value: Any) -> Optional[str]:
        """
        Parse an issue field or changelog value.

        Returns the value formatted according to the type.
        """

        raise NotImplementedError("Must be overridden in subclass")

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        # pylint: disable=unused-argument,no-self-use
        """
        Parse a changelog item and its parsed value.

        This is only called by changelog fields after the normal parse method.
        Returns the change value the original parsed value if that one should
        be used.
        """

        return value

    @property
    def table_name(self) -> Optional[str]:
        return None

    @property
    def table_key(self) -> TableKey:
        return None

class String_Parser(Field_Parser):
    """
    Parser for string fields.
    """

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        return str(value)

class Int_Parser(String_Parser):
    """
    Parser for integer fields.

    Currently converts the values to strings.
    """

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str) and '.' in value:
            logging.info('Decimal point in integer value: %s', value)
            value = value.split('.', 1)[0]

        return str(int(value))

class ID_Parser(Field_Parser):
    """
    Parser for identifier fields which may be missing.
    """

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        return str(int(value))

class Boolean_Parser(String_Parser):
    """
    Parser for string fields that only have two options: "Yes" or "No".
    """

    def parse(self, value: Any) -> Optional[str]:
        if value == "Yes":
            return str(1)
        if value == "No":
            return str(-1)
        if value is None or value == "":
            return None

        return value

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        return self.parse(change["fromString"])

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields, including date and time.
    """

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        return parse_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    def parse(self, value: Any) -> Optional[str]:
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

    def __init__(self, jira: Jira) -> None:
        super().__init__(jira)
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve data about all sprints for the project registered
        in Jira using the query API, and store the data in a table.
        """

        project_key = self.jira.project.jira_key
        for board in query.api.boards(projectKeyOrID=project_key):
            if hasattr(board, 'filter'):
                logging.info('Cannot prefetch sprints from old Agile API')
                return
            if hasattr(board, 'type') and board.type != 'scrum':
                logging.info('Skipping non-Scrum board #%d', board.id)
                continue

            for sprint in query.api.sprints(board.id, maxResults=False):
                self._parse_sprint_data(sprint.raw)

    @classmethod
    def _split_sprint(cls, sprint: str) -> Dict[str, str]:
        sprint_data: Dict[str, str] = {}
        sprint_string = parse_unicode(sprint)
        if '[' not in sprint_string:
            return sprint_data

        sprint_string = sprint_string[sprint_string.rindex('[')+1:-1]
        sprint_parts = sprint_string.split(',')
        prev_key = ""
        for part in sprint_parts:
            try:
                pair = part.split('=')
                if len(pair) == 1 and prev_key != '':
                    sprint_data[prev_key] = f"{sprint_data[prev_key]},{part}"
                else:
                    key = pair[0]
                    value = pair[1]
                    sprint_data[key] = value
                    prev_key = key
            except IndexError:
                return {}

        return sprint_data

    def parse(self, value: Any) -> Optional[str]:
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

            return ", ".join(sprints)

        return self._parse(value)

    @staticmethod
    def _has(sprint_data: Dict[str, str], key: str) -> bool:
        return key in sprint_data and sprint_data[key] != "<null>"

    def _parse(self, sprint: Any) -> Optional[str]:
        # Parse an individual sprint, add its data to the table and return the
        # sprint ID as an integer, or `None` if it is not an acceptable
        # sprint format.
        sprint_data = self._split_sprint(str(sprint))
        if not sprint_data:
            return None

        return str(self._parse_sprint_data(sprint_data))

    def _parse_sprint_data(self, sprint_data: Dict[str, str]) -> int:
        sprint_id = int(sprint_data["id"])

        row = {
            "id": str(sprint_id),
            "name": str(sprint_data["name"]),
        }

        if self._has(sprint_data, "endDate"):
            row["start_date"] = parse_date(sprint_data["startDate"])
        if self._has(sprint_data, "startDate"):
            row["end_date"] = parse_date(sprint_data["endDate"])
        if self._has(sprint_data, "completeDate"):
            row["complete_date"] = parse_date(sprint_data["completeDate"])

        if self._has(sprint_data, "goal"):
            row["goal"] = parse_unicode(sprint_data["goal"])
        if self._has(sprint_data, "rapidViewId"):
            row["board_id"] = str(sprint_data["rapidViewId"])
        if self._has(sprint_data, "originBoardId"):
            row["board_id"] = str(sprint_data["originBoardId"])

        self.jira.get_table("sprint").append(row)

        return sprint_id

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        if change['from'] is None or change['from'] == '':
            return None

        return change['from']

    @property
    def table_name(self) -> Optional[str]:
        return "sprint"

    @property
    def table_key(self) -> TableKey:
        return "id"

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        return str(float(value))

class Developer_Parser(Field_Parser):
    """
    Parser for fields that contain information about a JIRA user, including
    their account name and usually the display name.
    """

    def __init__(self, jira: Jira) -> None:
        super().__init__(jira)
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve data about all developers that are active within a project
        in Jira using the query API, and store the data in a table.
        """

        project_key = self.jira.project_key
        users = query.api.search_assignable_users_for_projects('', project_key)
        for user in users:
            self.parse(user)

    def parse(self, value: Any) -> Optional[str]:
        if value is not None and hasattr(value, "name"):
            encoded_name = parse_unicode(value.name)
            if value.name is not None and hasattr(value, "displayName"):
                self.jira.get_table("developer").append({
                    "name": encoded_name,
                    "display_name": parse_unicode(value.displayName),
                    "email": parse_unicode(value.emailAddress)
                })

            return encoded_name

        if isinstance(value, str):
            return parse_unicode(value)

        return None

    @property
    def table_name(self) -> Optional[str]:
        return "developer"

    @property
    def table_key(self) -> TableKey:
        return "name"

class Status_Category_Parser(Field_Parser):
    """
    Parser for subfields containing the status category.
    """

    def __init__(self, jira: Jira) -> None:
        super().__init__(jira)
        self.jira.register_table({
            "table": {
                "id": "int",
                "key": "str",
                "name": "unicode",
                "color": "unicode"
            }
        }, table_source=self)

    def parse(self, value: Any) -> Optional[str]:
        if value is not None:
            # Note: `value.id` is an integer, so return type and parameter type
            # for `Table.append` are technically incorrect. Error is hidden due
            # to the `Any` type. The importer now expects integers for these
            # tables (status and status_category).
            self.jira.get_table("status_category").append({
                "id": value.id,
                "key": str(value.key),
                "name": parse_unicode(value.name),
                "color": parse_unicode(value.colorName)
            })
            return value.id

        return None

    @property
    def table_name(self) -> Optional[str]:
        return "status_category"

    @property
    def table_key(self) -> TableKey:
        return "id"

class ID_List_Parser(Field_Parser):
    """
    Parser for fields that contain multiple items that have IDs, such as
    attachments.
    """

    def parse(self, value: Any) -> str:
        # Determine the number of items in the list.
        if value is None:
            return str(0)

        if not isinstance(value, list):
            # Singular value (changelogs)
            return str(1)

        id_list = [item.id for item in value]
        return str(len(id_list))

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        diff = -1 if value == str(0) else +1
        attachments = diffs.get("attachment", None)
        if attachments is not None:
            return str(int(attachments) + diff)

        return str(diff)

class Version_Parser(Field_Parser):
    """
    Parser for fields that contain the version in which an issue was fixed or
    which is affected by the issue.
    """

    def __init__(self, jira: Jira) -> None:
        super().__init__(jira)
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve data about all fix version releases for the project registered
        in Jira using the query API, and store the data in a table.
        """

        versions = query.api.project_versions(self.jira.project_key)
        self.parse(versions)

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, list):
            return str(value)

        encoded_value = None

        required_properties = ('id', 'name', 'released')
        for fix_version in value:
            if all(hasattr(fix_version, prop) for prop in required_properties):
                start_date = str(0)
                release_date = str(0)
                released = str(1) if fix_version.released else str(-1)
                description = parse_unicode(getattr(fix_version, 'description',
                                                    ""))
                if hasattr(fix_version, 'startDate'):
                    start_date = parse_date(fix_version.startDate)
                if hasattr(fix_version, 'releaseDate'):
                    release_date = parse_date(fix_version.releaseDate)

                encoded_value = str(fix_version.id)
                self.jira.get_table("fixVersion").append({
                    "id": encoded_value,
                    "name": str(fix_version.name),
                    "description": description,
                    "start_date": start_date,
                    "release_date": release_date,
                    "released": released
                })

        return encoded_value

    @property
    def table_name(self) -> Optional[str]:
        return "fixVersion"

    @property
    def table_key(self) -> TableKey:
        return "id"

class Rank_Parser(Field_Parser):
    """
    Parser for changelog fields that indicate whether the issue was ranked
    higher or lower on the backlog/storyboard.
    """

    def parse(self, value: Any) -> Optional[str]:
        return None

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
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

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        if change["fromString"] is not None:
            return change["fromString"]

        return None

class Flag_Parser(Field_Parser):
    """
    Parser for fields that mark the issue when it is set, such as an impediment.
    """

    def parse(self, value: Any) -> Optional[str]:
        # Output the flagged state as either "0" or "1".
        if (isinstance(value, list) and value) or value != "":
            return str(1)

        return str(0)

class Ready_Status_Parser(Field_Parser):
    """
    Parser for the 'ready status' field, which contains a visual indicator
    of whether the user story can be moved into a refinement or sprint.
    """

    def _add_to_table(self, encoded_id: str, html: str) -> None:
        match = re.match(r'<font .*><b>(.*)</b></font>', html)
        if match:
            name = match.group(1)
            self.jira.get_table("ready_status").append({
                "id": encoded_id,
                "name": name
            })

    def parse(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        encoded_value = None

        if hasattr(value, 'id') and hasattr(value, 'value'):
            encoded_value = str(value.id)
            self._add_to_table(encoded_value, value.value)

        return encoded_value

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        if change["from"] is not None:
            value = str(change["from"])
            self._add_to_table(value, change["fromString"])

        return value

    @property
    def table_name(self) -> Optional[str]:
        return "ready_status"

    @property
    def table_key(self) -> TableKey:
        return "id"

class Labels_Parser(Field_Parser):
    """
    Parser for fields that hold a list of labels.
    """

    def parse(self, value: Any) -> Optional[str]:
        # Count the number of labels.
        if isinstance(value, list):
            return str(len(value))
        if isinstance(value, str) and value != "":
            return str(len(value.split(' ')))

        return str(0)

class Project_Parser(Field_Parser):
    """
    Parser for fields that hold a project.
    """

    def __init__(self, jira: Jira) -> None:
        super().__init__(jira)

        self._projects: Dict[str, str] = {}
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve data about all projects known to us and keep a id-to-name
        mapping.
        """

        for project in query.api.projects():
            self.parse(project)

    def parse(self, value: Any) -> Optional[str]:
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

    def parse_changelog(self, change: Mapping[str, Any], value: Optional[str],
                        diffs: Dict[str, Optional[str]]) -> Optional[str]:
        if change["from"] is not None:
            project_id = str(change["from"])
            if project_id in self._projects:
                return self._projects[project_id]

            logging.info('Unknown old external project ID %s', project_id)

        return value
