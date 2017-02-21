"""
Module that handles issue changelog data.
"""

import logging

from .field import Changelog_Primary_Field, Changelog_Field

class Changelog(object):
    """
    Changelog parser.
    """

    def __init__(self, jira):
        self._jira = jira
        self._updated_since = self._jira.updated_since

        self._changelog_fields = {}
        self._changelog_primary_fields = {}

    def import_field_specification(self, name, data):
        """
        Import a JIRA field specification for a single field.

        This creates changelog field objects if necessary.
        """

        if "changelog_primary" in data:
            changelog_name = data["changelog_primary"]
            primary_field = Changelog_Primary_Field(self._jira, name, **data)
            self._changelog_primary_fields[changelog_name] = primary_field
        elif "changelog_name" in data:
            changelog_name = data["changelog_name"]
            changelog_field = Changelog_Field(self._jira, name, **data)
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
                logging.warning('Changelog entry has no updated date: %s',
                                repr(diffs))
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

    def get_versions(self, issue, data):
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

        if self._updated_since.is_newer(data["created"]):
            prev_diffs["updated"] = data["created"]
            new_data = self._create_change_transition(prev_data, prev_diffs)
            new_data["changelog_id"] = str(0)
            versions.append(new_data)

        return versions
