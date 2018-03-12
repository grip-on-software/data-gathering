"""
Module that handles issue changelog data.
"""

from builtins import str, object
import logging

from .base import Base_Changelog_Field
from .field import Changelog_Primary_Field, Changelog_Field
from ..utils import Sprint_Data

class Changelog(object):
    """
    Changelog parser.
    """

    def __init__(self, jira):
        self._jira = jira
        self._updated_since = self._jira.updated_since

        self._changelog_fields = {}
        self._changelog_primary_fields = {}

    def _create_field(self, changelog_class, name, data, field=None):
        if field is not None and isinstance(field, Base_Changelog_Field):
            return field

        return changelog_class(self._jira, name, **data)

    def import_field_specification(self, name, data, field=None):
        """
        Import a JIRA field specification for a single field.

        This creates changelog field objects if necessary.
        """

        if "changelog_primary" in data:
            changelog_name = data["changelog_primary"]
            primary_field = self._create_field(Changelog_Primary_Field, name,
                                               data, field=field)
            self._changelog_primary_fields[changelog_name] = primary_field
        elif "changelog_name" in data:
            changelog_name = data["changelog_name"]
            changelog_field = self._create_field(Changelog_Field, name, data,
                                                 field=field)
            self._changelog_fields[changelog_name] = changelog_field

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

            for field in self._changelog_primary_fields.values():
                value = field.parse_changelog(changes, diffs, issue)
                diffs[field.name] = value

            # Updated date is required for changelog sorting, as well as
            # issuelinks special field parser
            if "updated" not in diffs:
                logging.warning('Changelog entry has no updated date: %s',
                                repr(diffs))
                continue

            for item in changes.items:
                changelog_name = str(item.field)
                if changelog_name in self._changelog_fields:
                    field = self._changelog_fields[changelog_name]
                    value = field.parse_changelog(item, diffs, issue)
                    diffs[field.name] = value

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
        return dict(
            (key, value) for key, value in result.items() if value is not None
        )

    @classmethod
    def _update_field(cls, new_data, old_data, field):
        # Match the new_data field with the existence and the value of the same
        # field in old_data. This means that the field is deleted from new_data
        # if it did not exist in old_data.
        if field in old_data:
            new_data[field] = old_data[field]
        elif field in new_data:
            del new_data[field]

    @classmethod
    def _alter_change_metadata(cls, data, diffs, sprints):
        # Data is either a full changelog entry or a difference entry that is
        # applied to it after this call. Diffs is a difference entry with data
        # that may be partially for this change, but after this call it only
        # contains fields for for an earlier change.

        # Always use the updated_by and rank_change of the difference, even if
        # it is not available, instead of falling back to the 'newer' value if
        # the difference does not contain this field.
        cls._update_field(data, diffs, "updated_by")
        cls._update_field(data, diffs, "rank_change")

        if "sprint" in data and isinstance(data["sprint"], list):
            # Add the sprint list to the diff for the earlier change unless it
            # had a changelog entry, so that we keep on searching for the
            # correct sprint ID.
            if "sprint" not in diffs:
                diffs["sprint"] = data["sprint"]

            # Get updated datetime object of the current entry.
            if "updated" in data:
                updated = data["updated"]
            else:
                updated = data["created"]

            sprint_id = sprints.find_sprint(updated, sprint_ids=data["sprint"])
            if sprint_id is None:
                # Always take one of the sprints, even if they cannot be
                # matched to a sprint (due to start/end mismatch)
                data["sprint"] = str(data["sprint"][0])
            else:
                data["sprint"] = str(sprint_id)

    def _create_first_version(self, issue, prev_data, prev_diffs, sprints):
        self._update_field(prev_diffs, prev_data, "updated")
        self._update_field(prev_diffs, prev_data, "sprint")
        parser = self._jira.get_type_cast("developer")
        first_data = {
            "updated_by": parser.parse(issue.fields.creator)
        }

        self._alter_change_metadata(prev_diffs, first_data, sprints)
        new_data = self._create_change_transition(prev_data, prev_diffs)
        new_data["changelog_id"] = str(0)
        return new_data

    def get_versions(self, issue, data):
        """
        Fetch the versions of the issue based on changelog data as well as
        the current version of the issue.
        """

        issue_diffs = self.fetch_changelog(issue)
        sprints = Sprint_Data(self._jira.project,
                              sprints=self._jira.get_table("sprint").get())

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
                # Prepare difference between latest version and earlier one
                data["changelog_id"] = str(changelog_count)
                self._alter_change_metadata(data, diffs, sprints)
                versions.append(data)
                prev_diffs = diffs
                changelog_count -= 1
            else:
                prev_diffs["updated"] = updated
                self._alter_change_metadata(prev_diffs, diffs, sprints)
                old_data = self._create_change_transition(prev_data, prev_diffs)
                old_data["changelog_id"] = str(changelog_count)
                versions.append(old_data)
                prev_data = old_data
                prev_diffs = diffs
                changelog_count -= 1

        if self._updated_since.is_newer(data["created"]):
            prev_data["created"] = data["created"]
            first_data = self._create_first_version(issue, prev_data,
                                                    prev_diffs, sprints)
            versions.append(first_data)

        return versions

    @property
    def search_field(self):
        """
        Retrieve the field name necessary for changelog parsing.
        """

        return 'creator'
