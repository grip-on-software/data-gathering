"""
Tests for module that handles issue changelog data.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from typing import Dict, Optional
import unittest
from unittest.mock import Mock
from jira.resources import Attachment, Issue, IssueType, User
from jira.resilientsession import ResilientSession
from gatherer.domain.project import Project
from gatherer.jira.changelog import Changelog, Changes, ChangeHistory, ChangeItem
from gatherer.jira.collector import Collector
from gatherer.jira.field import Changelog_Item_Field, Changelog_Primary_Field

class ChangelogTest(unittest.TestCase):
    """
    Tests for changelog parser.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)
        session = ResilientSession()
        description_item = {
            'field': 'description',
            'fieldtype': 'jira',
            'from': None,
            'fromString': 'Initial description',
            'to': None,
            'toString': 'Intermediate description'
        }
        user_two = User({}, session, {
            'self': '',
            'name': 'testuser2',
            'displayName': 'Test User 2',
            'emailAddress': 'user@bar.test'
        })
        description_version = ChangeHistory({}, session, {
            'id': '997',
            'author': user_two,
            'created': '2024-04-22 12:34:56',
            'items': [ChangeItem({}, session, description_item)]
        })

        issuetype_item: Dict[str, Optional[str]] = {
            'field': 'issuetype',
            'fieldtype': 'jira',
            'from': '1',
            'fromString': 'Bug',
            'to': '5',
            'toString': 'Story'
        }
        user_three = User({}, session, {
            'self': '',
            'name': 'testuser3',
            'displayName': 'Test User 3',
            'emailAddress': 'user@baz.test'
        })
        issuetype_version = ChangeHistory({}, session, {
            'id': '999',
            'author': user_three,
            'created': '2024-04-23 00:11:22',
            'items': [ChangeItem({}, session, issuetype_item),
                      ChangeItem({}, session, {'field': 'other-test-field'})]
        })
        extra_item = {
            'field': 'description',
            'fieldtype': 'jira',
            'from': None,
            'fromString': 'Intermediate description',
            'to': None,
            'toString': 'Actual description'
        }
        attachment_item = {
            'field': 'Attachment',
            'fieldtype': 'jira',
            'from': None,
            'fromString': None,
            'to': '12345',
            'toString': 'picture.png'
        }
        extra_version = ChangeHistory({}, session, {
            'id': '998',
            'author': user_three,
            'created': '2024-04-23 00:11:22',
            'items': [ChangeItem({}, session, extra_item),
                      ChangeItem({}, session, attachment_item)]
        })

        issue_type = IssueType({}, session, {
            'self': '',
            'id': 5,
            'name': 'Story',
            'description': 'User story'
        })
        creator = User({}, session, {
            'self': '',
            'name': 'testuser',
            'displayName': 'Test User',
            'emailAddress': 'user@foo.test'
        })
        self.issue = Issue({}, session, {
            'self': '',
            'id': '99',
            'key': 'TEST-52',
            'fields': {
                'issuetype': issue_type,
                'description': 'Actual description',
                'created': '2024-04-22 11:00:00',
                'updated': '2024-04-23 00:11:22',
                'creator': creator,
                'attachment': Attachment({}, session, {
                    'self': '',
                    'id': '12345',
                    'filename': 'picture.png'
                })
            },
            'changelog': Changes({}, session, {
                'histories': [description_version, extra_version,
                              issuetype_version]
            })
        })
        self.changelog = self.jira.changelog
        self.expected_versions = [
            ('2024-04-22 11:00:00', {
                'issue_id': '99',
                'changelog_id': '0',
                'issuetype': '1',
                'created': '2024-04-22 11:00:00',
                'updated': '2024-04-22 11:00:00',
                'updated_by': 'testuser',
                'description': 'Initial description'
            }),
            ('2024-04-22 12:34:56', {
                'issue_id': '99',
                'changelog_id': '1',
                'issuetype': '1',
                'created': '2024-04-22 11:00:00',
                'updated': '2024-04-22 12:34:56',
                'updated_by': 'testuser2',
                'description': 'Intermediate description'
            }),
            ('2024-04-23 00:11:22', {
                'issue_id': '99',
                'changelog_id': '2',
                'issuetype': '5',
                'created': '2024-04-22 11:00:00',
                'updated': '2024-04-23 00:11:22',
                'updated_by': 'testuser3',
                'description': 'Actual description',
                'attachment': '1'
            })
        ]
        self.expected_fields = ({'description'},
                                {'description', 'issuetype', 'attachment'})

    def test_import_field_specification(self) -> None:
        """
        Test importing a JIRA field specification.
        """

        primary_field = self.changelog.import_field_specification('updated', {
            'field': 'updated',
            'changelog_primary': 'created',
            'type': 'date'
        })
        self.assertIsInstance(primary_field, Changelog_Primary_Field)
        self.assertEqual(primary_field,
                         self.changelog.get_primary_field('created'))

        item_field = self.changelog.import_field_specification('key', {
            'type': 'str',
            'changelog_name': 'Key',
            'primary': 'key'
        }, field=self.jira.get_issue_field('key'))
        self.assertIsInstance(item_field, Changelog_Item_Field)
        self.assertEqual(item_field, self.changelog.get_item_field('Key'))

        # If the field is a changelog field itself (e.g. a special field) then

        # If a field has no changelog information and is not a changelog field
        # parser itself, then no field is created.
        self.assertIsNone(self.changelog.import_field_specification('issue_id', {
            'type': 'int',
            'primary': 'id'
        }))

    def test_fetch_changelog(self) -> None:
        """
        Test extracting fields from the changelog of an issue.
        """

        # The latest version is not retrieved from the changelog yet, each diff
        # is indexed by its older date instead of the new version date, with
        # only the diff field and some primary fields in there, no metadata.
        diffs = self.changelog.fetch_changelog(self.issue)
        developers = self.jira.get_table('developer').get()
        # The two creators of the changelog versions are parsed, not the first
        # creator of the issue.
        self.assertNotIn({
            'name': 'testuser',
            'display_name': 'Test User',
            'email': 'user@foo.test'
        }, developers)
        self.assertIn({
            'name': 'testuser2',
            'display_name': 'Test User 2',
            'email': 'user@bar.test'
        }, developers)
        self.assertIn({
            'name': 'testuser3',
            'display_name': 'Test User 3',
            'email': 'user@baz.test'
        }, developers)
        self.assertEqual(len(diffs), 2)
        for ((_, old), (date, new), fields) in zip(self.expected_versions[:-1],
                                                   self.expected_versions[1:],
                                                   self.expected_fields):
            with self.subTest(date=date):
                expected_diff = new.copy()
                expected_diff.pop('issue_id')
                expected_diff.pop('changelog_id')
                expected_diff.pop('created')
                expected_diff['updated'] = date
                if 'attachment' in expected_diff:
                    expected_diff['attachment'] = '-1'

                for other_field in ('issuetype', 'description'):
                    if other_field in fields:
                        expected_diff[other_field] = old[other_field]
                    else:
                        expected_diff.pop(other_field)

                self.assertIn(date, diffs)
                self.assertEqual(diffs[date], expected_diff)

        # If no fields are imported into the changelog parser, then no diffs
        # will be available (need to at least parse the authors).
        changelog = Changelog(Mock(spec=Collector))
        self.assertEqual(changelog.fetch_changelog(self.issue), {})

    def test_get_versions(self) -> None:
        """
        Test fetching the versions of the issue.
        """

        data = self.jira.collect_fields(self.issue)
        versions = self.changelog.get_versions(self.issue, data)
        for version, (date, expected_version) in zip(reversed(versions),
                                                     self.expected_versions):
            with self.subTest(date=date):
                # Only check the fields that we expect in there, not any other
                # parsed fields from the specification that trickle through
                # from the latest version.
                self.assertTrue(set(expected_version.keys()).issubset(version.keys()),
                                msg=f"{expected_version!r} <= {version!r}")
                self.assertEqual({key: version[key] for key in expected_version},
                                 expected_version)
        self.assertEqual(len(versions), len(self.expected_versions))

        # If the updated date is too recent, then no versions are collected.
        jira = Collector(self.project, updated_since='2024-04-23 11:23')
        self.assertEqual(jira.changelog.get_versions(self.issue, data), [])
