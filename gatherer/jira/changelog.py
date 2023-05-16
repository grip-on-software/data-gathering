"""
Module that handles issue changelog data.

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
from typing import Dict, List, Mapping, MutableMapping, Optional, Type, TYPE_CHECKING
from jira import Issue
from .base import Base_Jira_Field, Base_Changelog_Field
from .field import Changelog_Primary_Field, Changelog_Field
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira, Field
else:
    Jira = object
    Field = object

class Changelog:
    """
    Changelog parser.
    """

    def __init__(self, jira: Jira) -> None:
        self._jira = jira
        self._updated_since = self._jira.updated_since

        self._changelog_fields: Dict[str, Base_Changelog_Field] = {}
        self._changelog_primary_fields: Dict[str, Base_Changelog_Field] = {}

    def _create_field(self, changelog_class: Type[Base_Changelog_Field],
                      name: str, data: Field,
                      field: Optional[Base_Jira_Field] = None) -> Base_Changelog_Field:
        if field is not None and isinstance(field, Base_Changelog_Field):
            return field

        return changelog_class(self._jira, name, **data)

    def import_field_specification(self, name: str, data: Field,
                                   field: Optional[Base_Jira_Field] = None) -> None:
        """
        Import a JIRA field specification for a single field.

        This creates changelog field objects if necessary.
        """

        if "changelog_primary" in data:
            changelog_name = str(data["changelog_primary"])
            primary_field = self._create_field(Changelog_Primary_Field, name,
                                               data, field=field)
            self._changelog_primary_fields[changelog_name] = primary_field
        elif "changelog_name" in data:
            changelog_name = str(data["changelog_name"])
            changelog_field = self._create_field(Changelog_Field, name, data,
                                                 field=field)
            self._changelog_fields[changelog_name] = changelog_field

    def fetch_changelog(self, issue: Issue) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Extract fields from the changelog of one issue. The resulting dictionary
        holds the differences of one change and is keyed by the update time,
        but it requires more postprocessing to be used in the output data.
        """

        changelog = issue.changelog.histories
        issue_diffs: Dict[str, Dict[str, Optional[str]]] = {}
        for changes in changelog:
            diffs: Dict[str, Optional[str]] = {}

            for field in self._changelog_primary_fields.values():
                value = field.parse_changelog(changes, diffs, issue)
                diffs[field.name] = value

            # Updated date is required for changelog sorting, as well as
            # issuelinks special field parser
            updated = diffs.get("updated", None)
            if updated is None:
                logging.warning('Changelog entry has no updated date: %s',
                                repr(diffs))
                continue

            for item in changes.items:
                changelog_name = str(item.field)
                if changelog_name in self._changelog_fields:
                    field = self._changelog_fields[changelog_name]
                    value = field.parse_changelog(item, diffs, issue)
                    diffs[field.name] = value

            if updated in issue_diffs:
                issue_diffs[updated].update(diffs)
            else:
                issue_diffs[updated] = diffs

        return issue_diffs

    @classmethod
    def _create_change_transition(cls, source_data: Mapping[str, Optional[str]],
                                  diffs: MutableMapping[str, Optional[str]]) -> Dict[str, str]:
        """
        Returns a copy of `source_data`, updated with the new key-value pairs
        in `diffs`.
        """

        # Shallow copy
        result = dict(source_data)

        # Count attachments
        attachments = diffs.pop("attachment", None)
        if attachments is not None and result["attachment"] is not None:
            total = int(result["attachment"]) + int(attachments)
            result["attachment"] = str(max(0, total))

        result.update(diffs)
        return cls._cleanup_data(result)

    @classmethod
    def _cleanup_data(cls, data: Dict[str, Optional[str]]) -> Dict[str, str]:
        return {
            key: value for key, value in data.items() if value is not None
        }

    @classmethod
    def _update_field(cls, new_data: MutableMapping[str, Optional[str]],
                      old_data: MutableMapping[str, Optional[str]], field: str) -> None:
        # Match the new_data field with the existence and the value of the same
        # field in old_data. This means that the field is deleted from new_data
        # if it did not exist in old_data.
        if field in old_data:
            new_data[field] = old_data[field]
        elif field in new_data:
            new_data[field] = None

    @classmethod
    def _alter_change_metadata(cls, data: MutableMapping[str, Optional[str]],
                               diffs: MutableMapping[str, Optional[str]]) -> None:
        # Data is either a full changelog entry or a difference entry that is
        # applied to it after this call. Diffs is a difference entry with data
        # that may be partially for this change, but after this call it only
        # contains fields for for an earlier change.

        # Always use the updated_by and rank_change of the difference, even if
        # it is not available, instead of falling back to the 'newer' value if
        # the difference does not contain this field.
        cls._update_field(data, diffs, "updated_by")
        cls._update_field(data, diffs, "rank_change")

        sprint = data.get("sprint", None)
        if sprint is not None and ", " in sprint:
            # Always take one of the sprints, even if they cannot be
            # matched to a sprint (due to start/end mismatch).
            # Prefer the latest sprint added.
            data["sprint"] = sprint.split(", ")[-1]

    def _create_first_version(self, issue: Issue,
                              prev_data: MutableMapping[str, Optional[str]],
                              prev_diffs: MutableMapping[str, Optional[str]]) -> Dict[str, str]:
        self._update_field(prev_diffs, prev_data, "updated")
        self._update_field(prev_diffs, prev_data, "sprint")
        parser = self._jira.get_type_cast("developer")
        first_data = {
            "updated_by": parser.parse(issue.fields.creator)
        }

        self._alter_change_metadata(prev_diffs, first_data)
        new_data = self._create_change_transition(prev_data, prev_diffs)
        new_data["changelog_id"] = str(0)
        return new_data

    def get_versions(self, issue: Issue,
                     data: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Fetch the versions of the issue based on changelog data as well as
        the current version of the issue.
        """

        issue_diffs = self.fetch_changelog(issue)

        changelog_count = len(issue_diffs)
        prev_diffs: Dict[str, Optional[str]] = {}
        prev_data: Dict[str, Optional[str]] = dict(data)
        versions: List[Dict[str, str]] = []

        # reestablish issue data from differences
        sorted_diffs = sorted(issue_diffs.keys(), reverse=True)
        for updated in sorted_diffs:
            if not self._updated_since.is_newer(updated):
                break

            diffs = issue_diffs[updated]
            if not prev_diffs:
                # Prepare difference between latest version and earlier one
                prev_data["changelog_id"] = str(changelog_count)
                self._alter_change_metadata(prev_data, diffs)
                data = self._cleanup_data(prev_data)
                versions.append(data)
                prev_diffs = diffs
                changelog_count -= 1
            else:
                prev_diffs["updated"] = updated
                self._alter_change_metadata(prev_diffs, diffs)
                old_data = self._create_change_transition(prev_data,
                                                          prev_diffs)
                old_data["changelog_id"] = str(changelog_count)
                versions.append(old_data)
                prev_data = {}
                prev_data.update(old_data)
                prev_diffs = diffs
                changelog_count -= 1

        if self._updated_since.is_newer(data["created"]):
            prev_data["created"] = data["created"]
            first_data = self._create_first_version(issue, prev_data,
                                                    prev_diffs)
            versions.append(first_data)

        return versions

    @property
    def search_field(self) -> str:
        """
        Retrieve the field name necessary for changelog parsing.
        """

        return 'creator'
