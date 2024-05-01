"""
Tests for module that defines type specific parsers that convert JIRA issue
field values.

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

from typing import Union
import unittest
from unittest.mock import MagicMock, Mock
from jira.resources import Attachment, Board, Project as JiraProject, Sprint, \
    StatusCategory, User, Version
from jira.resilientsession import ResilientSession
from gatherer.domain.project import Project
from gatherer.jira.collector import Collector
from gatherer.jira.parser import String_Parser, Int_Parser, ID_Parser, \
    Boolean_Parser, Date_Parser, Unicode_Parser, Sprint_Parser, \
    Decimal_Parser, Developer_Parser, Status_Category_Parser, ID_List_Parser, \
    Version_Parser, Rank_Parser, Issue_Key_Parser, Flag_Parser, Labels_Parser, \
    Project_Parser
from gatherer.jira.query import Query

class FieldParserTest(unittest.TestCase):
    """
    Base class for tests for parser of JIRA fields.
    """

    def setUp(self) -> None:
        # By default, we just provide a mock. Subclasses should replace this
        # if necessary.
        self.jira: Union[Mock, Collector] = Mock(spec=Collector)

class StringParserTest(FieldParserTest):
    """
    Tests for parser of string fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = String_Parser(self.jira)
        self.assertEqual(parser.parse('foobar'), 'foobar')
        self.assertIsNone(parser.parse(None))

class IntParserTest(FieldParserTest):
    """
    Tests for parser of integer fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Int_Parser(self.jira)
        self.assertEqual(parser.parse('3'), '3')
        self.assertEqual(parser.parse('3.5'), '3')
        self.assertEqual(parser.parse(4), '4')
        self.assertIsNone(parser.parse(None))

class IDParserTest(FieldParserTest):
    """
    Tests for parser of identifier fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = ID_Parser(self.jira)
        self.assertEqual(parser.parse('3'), '3')
        self.assertEqual(parser.parse(4), '4')

class BooleanParserTest(FieldParserTest):
    """
    Tests for parser of string fields with two options.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Boolean_Parser(self.jira)
        self.assertEqual(parser.parse('Yes'), '1')
        self.assertEqual(parser.parse('No'), '-1')
        self.assertEqual(parser.parse('other'), 'other')
        self.assertIsNone(parser.parse(''))
        self.assertIsNone(parser.parse(None))

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = Boolean_Parser(self.jira)
        self.assertEqual(parser.parse_changelog({'fromString': 'Yes'}, 't', {}),
                         '1')

class DateParserTest(FieldParserTest):
    """
    Tests for parser of timestamp fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Date_Parser(self.jira)
        self.assertEqual(parser.parse('2024-04-24T04:24:22Z'),
                         '2024-04-24 04:24:22')
        self.assertIsNone(parser.parse(None))

class UnicodeParserTest(FieldParserTest):
    """
    Tests for parser of fields that may include unicode characters.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Unicode_Parser(self.jira)
        self.assertEqual(parser.parse('foo\ud800bar'), 'foo?bar')
        self.assertIsNone(parser.parse(None))

class SprintParserTest(FieldParserTest):
    """
    Tests for parser of fields that may include unicode characters.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)

    def test_prefetch(self) -> None:
        """
        Test retrieving data about sprints for the project registered in JIRA.
        """

        parser = Sprint_Parser(self.jira)
        session = ResilientSession()

        query = MagicMock(spec=Query)
        attrs = {
            'boards.return_value': [
                Board({}, session, {
                    'self': '',
                    'type': 'scrum',
                    'id': 123
                }),
                Board({}, session, {
                    'self': '',
                    'type': 'kanban',
                    'id': 567
                })
            ],
            'sprints.return_value': [
                Sprint({}, session, {
                    'self': '',
                    'id': 90,
                    'name': 'Sprint #0',
                    'startDate': '2024-03-28T12:00:19Z',
                    'endDate': '2024-04-12T12:01:02Z',
                    'completeDate': '2024-04-11T17:15:13Z',
                    'goal': 'Description',
                    'rapidViewId': 123,
                    'originBoardId': 345
                })
            ]
        }
        query.api.configure_mock(**attrs)
        parser.prefetch(query)
        query.api.boards.assert_called_once_with(projectKeyOrID='TEST')
        query.api.sprints.assert_called_once_with(123, maxResults=False)
        table = self.jira.get_table('sprint')
        self.assertEqual(table.get(), [
            {
                'id': '90',
                'name': 'Sprint #0',
                'start_date': '2024-03-28 12:00:19',
                'end_date': '2024-04-12 12:01:02',
                'complete_date': '2024-04-11 17:15:13',
                'goal': 'Description',
                'board_id': '345'
            }
        ])

        attrs = {
            'boards.return_value': [
                Board({}, session, {
                    'self': '',
                    'filter': 'something',
                    'name': 'MyBoard'
                }),
                Board({}, session, {
                    'self': '',
                    'type': 'scrum',
                    'id': 890
                })
            ]
        }
        query.api.configure_mock(**attrs)
        table.clear()
        parser.prefetch(query)
        self.assertEqual(table.get(), [])

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Sprint_Parser(self.jira)
        self.assertEqual(parser.parse('Sprint[id=123,name=Foobar,goal=<null>]'),
                         '123')
        self.assertEqual(parser.parse('Sprint[id=456,name=Bar,baz]'), '456')
        self.assertEqual(parser.parse(['Sprint[id=123,name=Foobar,goal=ignore]',
                                       'Sprint[unparseable]',
                                       'Sprint[id=789,name=Baz,goal=ABC]']),
                                      '123, 789')
        self.assertIsNone(parser.parse('Sprint[]'))
        self.assertIsNone(parser.parse([]))
        self.assertIsNone(parser.parse('1234567890'))
        self.assertIsNone(parser.parse(None))
        self.assertEqual(self.jira.get_table("sprint").get(), [
            {
                'id': '123',
                'name': 'Foobar',
            },
            {
                'id': '456',
                'name': 'Bar,baz'
            },
            {
                'id': '789',
                'name': 'Baz',
                'goal': 'ABC'
            }
        ])

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = Sprint_Parser(self.jira)
        self.assertEqual(parser.parse_changelog({'from': 'Sprint1'}, '234', {}),
                         '234')
        self.assertIsNone(parser.parse_changelog({'from': None}, '', {}))
        self.assertIsNone(parser.parse_changelog({'from': ''}, '0', {}))

class DecimalParserTest(FieldParserTest):
    """
    Tests for parser of numeric fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Decimal_Parser(self.jira)
        self.assertEqual(parser.parse('3'), '3.0')
        self.assertEqual(parser.parse('3.5'), '3.5')
        self.assertEqual(parser.parse(4), '4.0')
        self.assertEqual(parser.parse(4.99), '4.99')
        self.assertIsNone(parser.parse(None))

class DeveloperParserTest(FieldParserTest):
    """
    Tests for parser of fields that contain information about a JIRA user.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)

        session = ResilientSession()
        self.user = User({}, session, {
            'self': '',
            'name': 'testuser',
            'displayName': 'Test User',
            'emailAddress': 'user@foo.test'
        })
        self.empty_user = User({}, session, {'self': '', 'name': '???'})

    def test_prefetch(self) -> None:
        """
        Test retrieving data about developers that are active within a project.
        """

        parser = Developer_Parser(self.jira)

        query = MagicMock(spec=Query)
        api_attrs = {
            'search_assignable_users_for_projects.return_value': [
                self.user, self.empty_user
            ]
        }
        query.api.configure_mock(**api_attrs)
        parser.prefetch(query)
        query.api.search_assignable_users_for_projects.assert_called_once_with('', 'TEST')
        self.assertEqual(self.jira.get_table('developer').get(), [
            {
                'name': 'testuser',
                'display_name': 'Test User',
                'email': 'user@foo.test'
            }
        ])

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Developer_Parser(self.jira)
        self.assertEqual(parser.parse('testuser'), 'testuser')
        self.assertIsNone(parser.parse(None))
        self.assertEqual(parser.parse(self.user), 'testuser')

class StatusCategoryParserTest(FieldParserTest):
    """
    Tests for parser of fields containing the status category.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Status_Category_Parser(self.jira)
        session = ResilientSession()
        category = StatusCategory({}, session, {
                'self': '',
            'id': '1',
            'key': 'fixed',
            'name': 'Fixed',
            'colorName': 'blue'
        })
        self.assertEqual(parser.parse(category), '1')
        self.assertIsNone(parser.parse(None))
        self.assertEqual(self.jira.get_table('status_category').get(), [
            {
                'id': '1',
                'key': 'fixed',
                'name': 'Fixed',
                'color': 'blue'
            }
        ])

class IDListParserTest(FieldParserTest):
    """
    Tests for parser of fields that contain multiple items that have IDs.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = ID_List_Parser(self.jira)
        session = ResilientSession()
        self.assertEqual(parser.parse([
            Attachment({}, session, {'self': '', 'id': 1}),
            Attachment({}, session, {'self': '', 'id': 42})
        ]), '2')
        self.assertEqual(parser.parse(None), '0')
        self.assertEqual(parser.parse(Attachment({}, session, {
            'self': '',
            'id': 3
        })), '1')

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = ID_List_Parser(self.jira)
        self.assertEqual(parser.parse_changelog({}, '0', {'attachment': '2'}),
                         '1')
        self.assertEqual(parser.parse_changelog({}, '1', {'attachment': '13'}),
                         '14')
        self.assertEqual(parser.parse_changelog({}, '1', {}), '1')

class VersionParserTest(FieldParserTest):
    """
    Tests for parser of fields that contain a version.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)

    def test_prefetch(self) -> None:
        """
        Test retrieving data about all fix versions of a project in JIRA.
        """

        parser = Version_Parser(self.jira)

        query = MagicMock(spec=Query)
        session = ResilientSession()
        version = Version({}, session, {
            'self': '',
            'id': 1,
            'name': 'Version 0.0.0',
            'released': True
        })
        full_version = Version({}, session, {
            'self': '',
            'id': 42,
            'name': 'Version 1.0.0',
            'released': False,
            'description': 'Milestone release',
            'startDate': '2017-01-01T08:00:00Z',
            'releaseDate': '2024-05-05T12:12:12Z'
        })
        api_attrs = {
            'project_versions.return_value': [
                version, full_version, Version({}, session, {'self': ''})
            ]
        }
        query.api.configure_mock(**api_attrs)
        parser.prefetch(query)
        query.api.project_versions.assert_called_once_with('TEST')
        self.assertEqual(self.jira.get_table('fixVersion').get(), [
            {
                'id': '1',
                'name': 'Version 0.0.0',
                'description': '',
                'start_date': '0',
                'release_date': '0',
                'released': '1'
            },
            {
                'id': '42',
                'name': 'Version 1.0.0',
                'description': 'Milestone release',
                'start_date': '2017-01-01 08:00:00',
                'release_date': '2024-05-05 12:12:12',
                'released': '-1'
            }
        ])

class RankParserTest(FieldParserTest):
    """
    Tests for parser of changelog fields that indicate whether an issue was
    ranked higher or lower.
    """

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = Rank_Parser(self.jira)
        self.assertEqual(parser.parse_changelog({'toString': 'Ranked lower'},
                                                None, {}),
                         '-1')
        self.assertEqual(parser.parse_changelog({'toString': 'Ranked higher'},
                                                None, {}),
                         '1')
        self.assertIsNone(parser.parse_changelog({'toString': 'Unknown value'},
                                                 None, {}))

class IssueKeyParserTest(FieldParserTest):
    """
    Tests for parser of fields that link to another issue.
    """

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = Issue_Key_Parser(self.jira)
        self.assertEqual(parser.parse_changelog({'fromString': 'TEST-123'},
                                                None, {}),
                         'TEST-123')
        self.assertIsNone(parser.parse_changelog({'fromString': None},
                                                 None, {}))

class FlagParserTest(FieldParserTest):
    """
    Tests for parser of fields that mark the issue.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Flag_Parser(self.jira)
        self.assertEqual(parser.parse('Flagged'), '1')
        self.assertEqual(parser.parse(['Multiple', 'flags']), '1')
        self.assertEqual(parser.parse(''), '0')

class LabelsParserTest(FieldParserTest):
    """
    Tests for parser of fields that hold a list of labels.
    """

    def test_parse(self) -> None:
        """
        Test parsing an issue field or changelog value.
        """

        parser = Labels_Parser(self.jira)
        self.assertEqual(parser.parse(['foo', 'bar']), '2')
        self.assertEqual(parser.parse('foo bar baz'), '3')
        self.assertEqual(parser.parse(''), '0')

class ProjectParserTest(FieldParserTest):
    """
    Tests for parser of fields that hold a project.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)
        self.query = MagicMock(spec=Query)
        session = ResilientSession()
        attrs = {
            'projects.return_value': [
                JiraProject({}, session, {'self': '', 'id': 23, 'key': 'EX'}),
                JiraProject({}, session, {'self': ''}),
                JiraProject({}, session, {'self': '', 'id': 22, 'key': 'TEST'})
            ]
        }
        self.query.api.configure_mock(**attrs)

    def test_prefetch(self) -> None:
        """
        Test retrieving data about all fix versions of a project in JIRA.
        """

        parser = Project_Parser(self.jira)
        parser.prefetch(self.query)
        self.query.api.projects.assert_called_once_with()

        self.assertEqual(parser.get_projects(), {
            '23': 'EX',
            '22': 'TEST'
        })

    def test_parse_changelog(self) -> None:
        """
        Test parsing a changelog item.
        """

        parser = Project_Parser(self.jira)
        parser.prefetch(self.query)
        self.assertEqual(parser.parse_changelog({'from': '23'}, None, {}), 'EX')
        self.assertIsNone(parser.parse_changelog({'from': '22'}, None, {}))
        # In case the field manages to retrieve a project, then it is returned.
        self.assertEqual(parser.parse_changelog({'from': None}, 'AB', {}), 'AB')
