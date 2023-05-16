"""
Special field parsers.

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

import logging
from typing import Any, Callable, Dict, Optional, Tuple, Type, cast, TYPE_CHECKING
from jira import Issue
from .base import Base_Jira_Field, Base_Changelog_Field, Table_Source, TableKey
from .query import Query
from ..table import Table
from ..utils import get_local_datetime, parse_unicode
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira, FieldValue
else:
    Jira = object
    FieldValue = object

S_type = Type['Special_Field']
SearchRows = Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]

class Special_Field(Base_Jira_Field):
    """
    A special field with additional data that cannot be parsed in conventional
    ways and is likely stored in a separate table.
    """

    _fields: Dict[str, S_type] = {}

    @classmethod
    def register(cls, field_name: str) -> Callable[[S_type], S_type]:
        """
        Decorator method for a special parser field class.
        """

        def decorator(subject: S_type) -> S_type:
            """
            Decorator that registers the class `subject` to the field name.
            """

            cls._fields[field_name] = subject
            return subject

        return decorator

    @classmethod
    def get_field_class(cls, field_name: str) -> S_type:
        """
        Retrieve a special field parser class for the given `field_name`.
        """

        return cls._fields[field_name]

    def parse(self, issue: Any):
        """
        Retrieve the field from an issue and collect relevant data within
        appropriate data storage.
        """

        if hasattr(issue.fields, self.name):
            field = getattr(issue.fields, self.name)
            if field is not None:
                self.collect(issue, field)

    def collect(self, issue: Any, field: Any) -> None:
        """
        Retrieve relevant data from the field belonging to the issue,
        and store the data where appropriate.
        """

        raise NotImplementedError("Subclasses must override this method")

    @property
    def table_name(self) -> str:
        raise NotImplementedError("Subclasses must override this property")

    @property
    def search_field(self) -> Optional[str]:
        return self.name

@Special_Field.register("comment")
class Comment_Field(Special_Field):
    """
    Field parser for the comments of a JIRA issue.
    """

    def __init__(self, jira: Jira, name: str, **info: FieldValue) -> None:
        super().__init__(jira, name, **info)
        self._table = cast(Dict[str, str], self.data.get("table", {}))
        self._comment_fields = cast(Dict[str, str], self.data.get("fields", {}))

    def collect(self, issue: Any, field: Any) -> None:
        if not hasattr(field, 'comments'):
            return

        for comment in field.comments:
            self._collect_comment(issue, comment)

    def _collect_comment(self, issue: Any, comment: Any) -> None:
        row: Dict[str, str] = {}
        is_newer = False
        for subfield, datatype in self._table.items():
            if subfield in self._comment_fields:
                fieldname = self._comment_fields[subfield]
            else:
                fieldname = subfield

            if hasattr(comment, fieldname):
                prop = getattr(comment, fieldname)
                parser = self.jira.get_type_cast(datatype)
                value = parser.parse(prop)
            if value is not None:
                row[subfield] = value
            else:
                row[subfield] = str(0)

            if datatype == 'date' and self.jira.updated_since.is_newer(row[subfield]):
                is_newer = True

        row["issue_id"] = str(issue.id)
        if is_newer:
            self.jira.get_table("comments").append(row)

    @property
    def table_name(self) -> str:
        return "comments"

    @property
    def table_key(self) -> Optional[str]:
        return "id"

class Special_Changelog_Field(Special_Field, Base_Changelog_Field):
    """
    Abstract base class for a special field which makes use of the changelog
    to collect start and end dates of a range in between when a field contained
    a value.
    """

    _changelog_map = {
        'to': 'start_date',
        'from': 'end_date'
    }

    @property
    def table(self) -> Table:
        """
        Retrieve a table used by this field to store its values.

        This table may be used for outputting the data of this field, searching
        for existing rows and updating rows with new values.
        """

        return self.jira.get_table(self.table_name)

    def search_row(self, data: Dict[str, Optional[str]], issue: Issue,
                   entry_field: str) -> SearchRows:
        """
        Find a row that was collected for this issue prior that matches the
        properties of this version, to determine whether the value has existed
        prior. The matched row is stored in the same key-based or link-based
        table as the `table` property.

        Returns both the partial row used to search for the matching row, and
        the found row itself. The partial row must also be useful for appending
        or updating rows. The partial row may be `None` to indicate that no
        match could be made at all and no row should be added either. The found
        row may also be `None` to indicate that there is no existing row that
        meets the criteria.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def parse_changelog(self, entry: Any, diffs: Dict[str, Optional[str]],
                        issue: Issue):
        data = entry.__dict__
        self.check_changelog(data, diffs, issue, 'to')
        self.check_changelog(data, diffs, issue, 'from')

    def check_changelog(self, data: Dict[str, Optional[str]],
                        diffs: Dict[str, Optional[str]], issue: Issue,
                        entry_field: str) -> None:
        """
        Check whether a changelog entry ('from' or 'to') provides useful data
        and update or append the data to the table.
        """

        # If the changelog item is missing to/from entries, then ignore that
        # part silently.
        if data[entry_field] is None or diffs["updated"] is None:
            return

        # Search for the row
        match_row, found_row = self.search_row(data, issue, entry_field)
        if match_row is None:
            # We could not create a pattern row to match against in the first
            # place, so ignore the entry field.
            return

        update_field = self._changelog_map[entry_field]
        if found_row is None:
            # Create a new row.
            match_row.update({
                "start_date": str(0),
                "end_date": str(0)
            })
            match_row[update_field] = diffs["updated"]
            self.table.append(match_row)
            return

        if found_row[update_field] != str(0):
            # Links may be added and removed multiple times; we keep the
            # earliest start date and latest end date of the link.
            # We log the circumstances in case this happens too often.
            older = get_local_datetime(diffs["updated"]) < \
                    get_local_datetime(found_row[update_field])
            key = str(issue.key)
            if older and update_field == "end_date":
                logging.info("Older %s end date in %s: %s, %s", self.table_name,
                             key, diffs['updated'], found_row[update_field])
                return
            if not older and update_field == "start_date":
                logging.info("Newer %s start date in %s: %s, %s",
                             self.table_name, key, diffs["updated"],
                             found_row[update_field])
                return

        # Update the row to contain the new date.
        self.table.update(match_row, {update_field: diffs["updated"]})

class Component_Table(Table_Source):
    """
    Source definition for an additional components table.
    """

    @property
    def table_key(self) -> TableKey:
        return "id"

    @property
    def table_name(self) -> Optional[str]:
        return "component"

@Special_Field.register("components")
class Component_Field(Special_Changelog_Field):
    """
    Field parser for the components related to an issue.
    """

    def __init__(self, jira: Jira, name: str, **info: FieldValue) -> None:
        super().__init__(jira, name, **info)
        self.jira.register_table({
            "table": {
                "name": "unicode",
                "description": "unicode"
            },
        }, table_source=Component_Table())
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve all components from the query API.
        """

        components = query.api.project_components(self.jira.project.jira_key)
        for component in components:
            self._add_component(component)

    def _add_component(self, component: Any) -> None:
        if hasattr(component, "description"):
            description = parse_unicode(component.description)
        else:
            description = str(0)

        self.jira.get_table("component").append({
            "id": str(component.id),
            "name": parse_unicode(component.name),
            "description": description
        })

    def collect(self, issue: Any, field: Any) -> None:
        for component in field:
            self._add_component(component)
            self.table.append({
                "issue_id": str(issue.id),
                "component_id": str(component.id),
                "start_date": str(0),
                "end_date": str(0),
            })

    def search_row(self, data: Dict[str, Optional[str]], issue: Issue,
                   entry_field: str) -> SearchRows:
        match_row = {
            "issue_id": str(issue.id),
            "component_id": str(data[entry_field])
        }
        found_row = self.table.get_row(match_row)

        return match_row, found_row

    @property
    def table_name(self) -> str:
        return "issue_component"

    @property
    def table_key(self) -> TableKey:
        return ("issue_id", "component_id")

@Special_Field.register("issuelinks")
class Issue_Link_Field(Special_Changelog_Field):
    """
    Field parser for the issue links related to an issue.
    """

    def __init__(self, jira: Jira, name: str, **info: FieldValue) -> None:
        super().__init__(jira, name, **info)
        self._relations: Dict[str, Dict[str, str]] = {}
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query: Query) -> None:
        """
        Retrieve all relationship types from the query API.
        """

        relationships = query.api.issue_link_types()
        table = self.jira.get_table("relationshiptype")
        for relationship in relationships:
            relation_id = str(relationship.id)
            inward = str(relationship.inward)
            outward = str(relationship.outward)
            self._relations[inward] = {
                'id': relation_id,
                'outward': str(-1)
            }
            self._relations[outward] = {
                'id': relation_id,
                'outward': str(1)
            }
            table.append({
                'id': relation_id,
                'name': str(relationship.name),
                'inward': inward,
                'outward': outward
            })

    def collect(self, issue: Any, field: Any) -> None:
        for issuelink in field:
            if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                continue


            self._check_link(issue, issuelink, outward=True)
            self._check_link(issue, issuelink, outward=False)

    def _check_link(self, issue: Any, issuelink: Any, outward: bool = True) -> None:
        if outward:
            attr = 'outwardIssue'
            direction = str(1)
        else:
            attr = 'inwardIssue'
            direction = str(-1)

        if hasattr(issuelink, attr):
            prop = getattr(issuelink, attr)
            from_key = str(issue.key)
            to_key = str(prop.key)
            self.jira.get_table("issuelinks").append({
                'from_key': from_key,
                'to_key': to_key,
                'relationshiptype': str(issuelink.type.id),
                'outward': direction,
                'start_date': str(0),
                'end_date': str(0)
            })

    def search_row(self, data: Dict[str, Optional[str]], issue: Issue,
                   entry_field: str) -> SearchRows:
        from_key = str(issue.key)
        text = data[f'{entry_field}String']
        if text is None:
            return None, None

        search_row = {
            'from_key': from_key,
            'to_key': str(data[entry_field])
        }
        match_row: Dict[str, str] = {}
        row = None
        for relation, candidate in self._relations.items():
            if relation in text:
                # Find a row with this relation. We only stop if we find such
                # a row, because we might have relations with conflicting
                # (similar) inward/outward names. This way, we check for other
                # relations if we did not add a row from another change or the
                # payload field, which is likely to happen for exact matches.
                match_row = search_row.copy()
                match_row.update({
                    'relationshiptype': candidate['id'],
                    'outward': candidate['outward']
                })
                row = self.table.get_row(match_row)
                if row is not None:
                    break

        if not match_row:
            # Cannot deduce relation
            logging.warning('Cannot deduce relation from changelog: %s', text)
            return None, None

        return match_row, row

    @property
    def table_name(self) -> str:
        return "issuelinks"

    @property
    def table_key(self) -> TableKey:
        return ('from_key', 'to_key', 'relationshiptype', 'outward')

@Special_Field.register("subtasks")
class Subtask_Field(Special_Field):
    """
    Field parser for the subtasks related to an issue.
    """

    def collect(self, issue: Any, field: Any) -> None:
        for subtask in field:
            self.jira.get_table("subtasks").append({
                'from_id': str(issue.id),
                'to_id': str(subtask.id)
            })

    @property
    def table_name(self) -> str:
        return "subtasks"

    @property
    def table_key(self) -> TableKey:
        return ('from_id', 'to_id')
