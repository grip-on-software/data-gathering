"""
Tests for module that defines special field parsers.

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

from typing import Optional
import unittest
from unittest.mock import MagicMock, Mock
from jira.resources import Comment, Component, Issue, IssueLink, \
    IssueLinkType, UnknownResource, User
from jira.resilientsession import ResilientSession
from gatherer.domain.project import Project
from gatherer.jira.changelog import ChangeHistory, ChangeItem
from gatherer.jira.collector import Collector, FieldValue
from gatherer.jira.special_field import ResourceList, Special_Field, \
    Comment_Field, Component_Field, Issue_Link_Field, Subtask_Field
from gatherer.jira.query import Query

@Special_Field.register("test")
class Test_Field(Special_Field):
    """
    Test field parser to demonstrate registering special fields.
    """

    def __init__(self, jira: Collector, name: str, **info: FieldValue):
        super().__init__(jira, name, **info)
        self.collected_field: ResourceList = []

    def collect(self, issue: Issue, field: ResourceList) -> None:
        self.collected_field = field

    @property
    def table_name(self) -> str:
        return 'test'

    @property
    def table_key(self) -> Optional[str]:
        return None

class SpecialFieldRegisterTest(unittest.TestCase):
    """
    Tests for registering special field parsers.
    """

    def test_get_field_class(self) -> None:
        """
        Test retrieving a special field parser class.
        """

        field_class = Special_Field.get_field_class('test')
        self.assertEqual(field_class, Test_Field)

        # The field is functional.
        field = field_class(Mock(spec=Collector), 'abc')
        if not isinstance(field, Test_Field): # pragma: no cover
            self.fail("Incorrect special field")

        session = ResilientSession()
        data = UnknownResource({}, session, {
            'self': '',
            'key': 'foo'
        })
        self.assertIsNone(field.parse(Issue({}, session, {
            'self': '',
            'fields': {'abc': [data]}
        })))
        self.assertEqual(field.collected_field, [data])

class SpecialFieldTest(unittest.TestCase):
    """
    Base class for tests for parser of unconventional JIRA fields.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)

class CommentFieldTest(SpecialFieldTest):
    """
    Tests for field parser of the comments in a JIRA issue.
    """

    def setUp(self) -> None:
        super().setUp()
        session = ResilientSession()
        user_one = User({}, session, {
            'self': '',
            'name': 'testuser',
            'displayName': 'Test User',
            'emailAddress': 'user@foo.test'
        })
        user_two = User({}, session, {
            'self': '',
            'name': 'testuser2'
        })
        self.comments: ResourceList = [
            Comment({}, session, {
                'self': '',
                'id': '445',
                'author': user_one,
                'body': 'We are successful',
                'updateAuthor': user_two,
                'created': '2024-04-26T14:56:04Z',
                'updated': '2024-04-26T16:33:15Z'
            }),
            # Empty comment is ignored due to no date fields
            Comment({}, session, {'self': ''})
        ]
        self.issue = Issue({}, session, {
            'self': '',
            'id': '123',
            'fields': {'comment': {'comments': self.comments}}
        })
        table: FieldValue = {
            "id": "int",
            "issue_id": "int",
            "comment": "unicode",
            "author": "developer",
            "created_at": "date",
            "updater": "developer",
            "updated_at": "date"
        }
        fields: FieldValue = {
            "comment": "body",
            "created_at": "created",
            "updater": "updateAuthor",
            "updated_at": "updated"
        }
        self.field = Comment_Field(self.jira, 'comment', table=table,
                                   fields=fields)

    def test_fetch(self) -> None:
        """
        Test retrieving the field from an issue for iteration.
        """

        self.assertEqual(self.field.fetch(self.issue), self.comments)

    def test_collect(self) -> None:
        """
        Test retrieving relevant data from the field belonging to the issue.
        """

        self.field.collect(self.issue, self.comments)
        self.assertEqual(self.jira.get_table('comments').get(), [
            {
                'id': '445',
                'issue_id': '123',
                'comment': 'We are successful',
                'author': 'testuser',
                'created_at': '2024-04-26 14:56:04',
                'updater': 'testuser2',
                'updated_at': '2024-04-26 16:33:15'
            }
        ])

class ComponentFieldTest(SpecialFieldTest):
    """
    Tests for field parser of the components related to an issue.
    """

    def setUp(self) -> None:
        super().setUp()
        self.field = Component_Field(self.jira, 'components', table={
            'issue_id': 'int',
            'component_id': 'int'
        })

        session = ResilientSession()
        component = Component({}, session, {
            'self': '',
            'id': '555',
            'name': 'lib',
            'description': 'Library'
        })
        undescribed = Component({}, session, {
            'self': '',
            'id': '313',
            'name': 'pack'
        })
        self.components: ResourceList = [component, undescribed]
        self.issue = Issue({}, session, {
            'self': '',
            'id': '123',
            'key': 'TEST-10',
            'fields': {'components': [component]}
        })

        self.expected_component_table = [
            {
                'id': '555',
                'name': 'lib',
                'description': 'Library'
            },
            {
                'id': '313',
                'name': 'pack',
                'description': '0'
            }
        ]
        self.expected_issue_table = [
            {
                'issue_id': '123',
                'component_id': '555',
                'start_date': '0',
                'end_date': '0'
            }
        ]

    def test_prefetch(self) -> None:
        """
        Test retrieving all components for a project from the JIRA query API.
        """

        query = MagicMock(spec=Query)
        attrs = {
            'project_components.return_value': self.components
        }
        query.api.configure_mock(**attrs)

        self.field.prefetch(query)
        query.api.project_components.assert_called_once_with('TEST')

        self.assertEqual(self.jira.get_table('component').get(),
                         self.expected_component_table)

    def test_collect(self) -> None:
        """
        Test retrieving relevant data from the field belonging to the issue.
        """

        self.field.collect(self.issue, [self.components[0]])
        self.assertEqual(self.jira.get_table('component').get(),
                         [self.expected_component_table[0]])
        self.assertEqual(self.jira.get_table('issue_component').get(),
                         self.expected_issue_table)

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        diffs = {'updated': '2024-04-25 15:20:40', 'other': None}
        session = ResilientSession()
        to_item = ChangeItem({}, session, {'to': '555', 'from': None})
        from_item = ChangeItem({}, session, {'to': None, 'from': '555'})

        self.field.collect(self.issue, [self.components[0]])
        table = self.jira.get_table('issue_component')
        self.assertEqual(table.get(), self.expected_issue_table)

        entry = ChangeHistory({}, session, {})
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     to_item))
        self.assertEqual(table.get(), [
            {
                'issue_id': '123',
                'component_id': '555',
                'start_date': '2024-04-25 15:20:40',
                'end_date': '0'
            }
        ])

        diffs = {'updated': '2024-04-25 16:21:42'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     from_item))
        self.assertEqual(table.get(), [
            {
                'issue_id': '123',
                'component_id': '555',
                'start_date': '2024-04-25 15:20:40',
                'end_date': '2024-04-25 16:21:42'
            }
        ])

        # Earlier start date is updated.
        diffs = {'updated': '2024-04-25 14:29:49'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     to_item))
        self.assertEqual(table.get(), [
            {
                'issue_id': '123',
                'component_id': '555',
                'start_date': '2024-04-25 14:29:49',
                'end_date': '2024-04-25 16:21:42'
            }
        ])

        # Later end date is updated.
        diffs = {'updated': '2024-04-25 17:22:44'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     from_item))
        final_table = [
            {
                'issue_id': '123',
                'component_id': '555',
                'start_date': '2024-04-25 14:29:49',
                'end_date': '2024-04-25 17:22:44'
            }
        ]
        self.assertEqual(table.get(), final_table)

        # Later start date is not updated.
        diffs = {'updated': '2024-04-25 14:44:44'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     to_item))
        self.assertEqual(table.get(), final_table)

        # Earlier end date is not updated.
        diffs = {'updated': '2024-04-25 17:15:13'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     from_item))
        self.assertEqual(table.get(), final_table)

        # Empty changelog field does not alter the table.
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     None))
        self.assertEqual(table.get(), final_table)

        # Changelog field for unknown component(s) are added.
        other_item = ChangeItem({}, session, {'from': '313', 'to': '217'})
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     other_item))
        actual_table = table.get()
        self.assertIn(final_table[0], actual_table)
        self.assertIn({
            'issue_id': '123',
            'component_id': '217',
            'start_date': '2024-04-25 17:15:13',
            'end_date': '0'
        }, actual_table)
        self.assertIn({
            'issue_id': '123',
            'component_id': '313',
            'start_date': '0',
            'end_date': '2024-04-25 17:15:13'
        }, actual_table)
        self.assertEqual(len(actual_table), 3)

class IssueLinkFieldTest(SpecialFieldTest):
    """
    Tests for field parser of the issue links.
    """

    def setUp(self) -> None:
        super().setUp()
        self.field = Issue_Link_Field(self.jira, 'issuelinks', table={
            "from_id": "int",
            "to_id": "int",
            "relationshiptype": "int",
            "outward": "boolean"
        })

        session = ResilientSession()
        relationship = IssueLinkType({}, session, {
            'self': '',
            'id': '4',
            'name': 'Link',
            'inward': 'linked by',
            'outward': 'links to'
        })
        self.types: ResourceList = [relationship]

        link = IssueLink({}, session, {
            'self': '',
            'type': relationship,
            'outwardIssue': Issue({}, session, {
                'self': '',
                'id': '456',
                'key': 'TEST-42'
            })
        })
        empty = IssueLink({}, session, {'self': '', 'type': None})
        self.links: ResourceList = [link, empty]
        self.issue = Issue({}, session, {
            'self': '',
            'id': '123',
            'key': 'TEST-10',
            'fields': {'issuelinks': self.links}
        })

        self.expected_type_table = [
            {
                'id': '4',
                'name': 'Link',
                'inward': 'linked by',
                'outward': 'links to'
            }
        ]
        self.expected_issue_table = [
            {
                'from_key': 'TEST-10',
                'to_key': 'TEST-42',
                'relationshiptype': '4',
                'outward': '1',
                'start_date': '0',
                'end_date': '0'
            }
        ]

    def test_prefetch(self) -> None:
        """
        Test retrieving all components for a project from the JIRA query API.
        """

        query = MagicMock(spec=Query)
        attrs = {
            'issue_link_types.return_value': self.types
        }
        query.api.configure_mock(**attrs)

        self.field.prefetch(query)
        query.api.issue_link_types.assert_called_once_with()

        self.assertEqual(self.jira.get_table('relationshiptype').get(),
                         self.expected_type_table)

    def test_collect(self) -> None:
        """
        Test retrieving relevant data from the field belonging to the issue.
        """

        self.field.collect(self.issue, self.links)
        self.assertEqual(self.jira.get_table('issuelinks').get(),
                         self.expected_issue_table)

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        diffs = {'updated': '2024-04-26 16:30:50', 'other': None}
        session = ResilientSession()
        to_item = ChangeItem({}, session, {
            'to': 'TEST-42',
            'toString': 'This issue links to TEST-42',
            'from': None,
            'fromString': None
        })
        from_item = ChangeItem({}, session, {
            'to': None,
            'toString': None,
            'from': 'TEST-42',
            'fromString': 'This issue links to TEST-42'
        })

        # Need to prefetch relationship types and fill table with expected row.
        query = MagicMock(spec=Query)
        attrs = {
            'issue_link_types.return_value': self.types
        }
        query.api.configure_mock(**attrs)

        self.field.prefetch(query)

        self.field.collect(self.issue, self.links)

        table = self.jira.get_table('issuelinks')
        self.assertEqual(table.get(), self.expected_issue_table)

        entry = ChangeHistory({}, session, {})
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     to_item))
        expected_row = self.expected_issue_table[0].copy()
        expected_row['start_date'] = '2024-04-26 16:30:50'
        self.assertEqual(table.get(), [expected_row])

        diffs = {'updated': '2024-04-26 18:24:14'}
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     from_item))
        expected_row['end_date'] = '2024-04-26 18:24:14'
        self.assertEqual(table.get(), [expected_row])

        # Changelog item with unknown relation type text or missing issue key
        # does not alter the table.
        unknown_item = ChangeItem({}, session, {
            'from': 'INV-175',
            'fromString': None,
            'to': 'EX-455',
            'toString': 'This issue has a special connection to EX-455'
        })
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     unknown_item))
        self.assertEqual(table.get(), [expected_row])

        # Changelog with unknown issue does alter the table.
        diffs = {'updated': '2024-04-26 10:12:14'}
        missing_item = ChangeItem({}, session, {
            'from': 'INV-9',
            'fromString': 'This issue is linked by INV-9',
            'to': None,
            'toString': None
        })
        self.assertIsNone(self.field.parse_changelog(entry, diffs, self.issue,
                                                     missing_item))
        final_table = table.get()
        self.assertIn(expected_row, final_table)
        self.assertIn({
            'from_key': 'TEST-10',
            'to_key': 'INV-9',
            'relationshiptype': '4',
            'outward': '-1',
            'start_date': '0',
            'end_date': '2024-04-26 10:12:14'
        }, final_table)
        self.assertEqual(len(final_table), 2)

class SubtaskFieldTest(SpecialFieldTest):
    """
    Tests for field parser of the subtasks related to an issue.
    """

    def test_collect(self) -> None:
        """
        Test retrieving relevant data from the field belonging to the issue.
        """

        field = Subtask_Field(self.jira, 'subtasks', table={
            'from_id': 'int',
            'to_id': 'int'
        })
        session = ResilientSession()
        subtasks: ResourceList = [Issue({}, session, {'self': '', 'id': '456'})]
        issue = Issue({}, session, {
            'self': '',
            'id': '123',
            'fields': {'subtasks': subtasks}
        })
        field.collect(issue, subtasks)
        self.assertEqual(self.jira.get_table('subtasks').get(), [
            {
                'from_id': '123',
                'to_id': '456'
            }
        ])
