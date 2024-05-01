"""
Tests for collector for extracting data from the JIRA API.

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

from typing import Dict, Optional, Type, Union
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock, Mock
from jira import Issue, JIRA, JIRAError
from jira.resources import IssueType, User
from jira.resilientsession import ResilientSession
from gatherer.domain.project import Project
from gatherer.domain.source import Source, Jira
from gatherer.jira.base import TableKey, Table_Source
from gatherer.jira.changelog import Changes
from gatherer.jira.collector import Collector
from gatherer.jira.field import Primary_Field, Property_Field, Payload_Field
from gatherer.jira.special_field import Subtask_Field
from gatherer.jira.update import Update_Tracker
from gatherer.table import Table, Key_Table, Link_Table

class EmptyTableSource(Table_Source):
    """
    Table source without table names or keys.
    """

    @property
    def table_key(self) -> TableKey:
        return None

    @property
    def table_name(self) -> Optional[str]:
        return None

class TestTableSource(Table_Source):
    """
    Table source for a test table.
    """

    @property
    def table_key(self) -> TableKey:
        return None

    @property
    def table_name(self) -> Optional[str]:
        return 'test_table'

class LinkTableSource(Table_Source):
    """
    Table source for a link table.
    """

    @property
    def table_key(self) -> TableKey:
        return ('from', 'to')

    @property
    def table_name(self) -> Optional[str]:
        return 'test_link'

class CollectorTest(unittest.TestCase):
    """
    Tests for JIRA collection and extraction class.
    """

    def setUp(self) -> None:
        self.project = Project('TEST')
        self.jira = Collector(self.project)
        session = ResilientSession()
        issue_type = IssueType({}, session, {
            'self': '',
            'id': '5',
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
                'created': '2024-04-22 11:00:00',
                'updated': '2024-04-23 00:11:22',
                'creator': creator
            },
            'changelog': Changes({}, session, {'histories': []})
        })

    def test_register_issue_field(self) -> None:
        """
        Test creating a field to fetch information from issue data.
        """

        field = self.jira.register_issue_field('issue_id', {
            'type': 'int',
            'primary': 'id'
        })
        self.assertIsInstance(field, Primary_Field)
        self.assertEqual(field, self.jira.get_issue_field('issue_id'))

        # 'property' field must also have a 'field' in its data.
        with self.assertRaises(KeyError):
            self.jira.register_issue_field('prop', {'property': 'id'})

        self.assertIsInstance(self.jira.register_issue_field('issuetype', {
            'field': 'issuetype',
            'property': 'id',
            'type': 'identifier'
        }), Property_Field)

        self.assertIsInstance(self.jira.register_issue_field('created', {
            'field': 'created',
            'type': 'date'
        }), Payload_Field)

        # Special field
        self.assertIsInstance(self.jira.register_issue_field('subtasks', {
            'special_parser': 'subtasks',
            'table': {
                'from_id': 'int',
                'to_id': 'int'
            }
        }), Subtask_Field)

    def test_register_table(self) -> None:
        """
        Test creating a table storage according to a specification.
        """

        empty = EmptyTableSource()
        source = TestTableSource()
        link = LinkTableSource()

        self.assertIsNone(self.jira.register_table({}, source))
        self.assertIsNone(self.jira.register_table({
            "table": {},
            "type": "int",
            "table_options": {}
        }, empty))

        table = self.jira.register_table({"table": "test"}, source)
        if not isinstance(table, Table): # pragma: no cover
            self.fail("Registered table is not a Table")
        self.assertEqual(table, self.jira.get_table("test"))
        self.assertEqual(table.name, "test")

        mapped = self.jira.register_table({"table": {}}, source)
        if not isinstance(mapped, Table): # pragma: no cover
            self.fail("Registered table is not a Table")
        self.assertEqual(mapped, self.jira.get_table("test_table"))
        self.assertEqual(mapped.name, "test_table")

        key_table = self.jira.register_table({
            "table": {},
            "type": "sprint",
            "table_options": {
                "filename": "data_test_sprint.json"
            }
        }, empty)
        if not isinstance(key_table, Key_Table): # pragma: no cover
            self.fail("Registered table is not a Key_Table")
        self.assertEqual(key_table, self.jira.get_table("sprint"))
        self.assertEqual(key_table.name, "sprint")
        self.assertEqual(key_table.filename, "data_test_sprint.json")

        link_table = self.jira.register_table({
            "table": "test_issue_link",
        }, link)
        if not isinstance(link_table, Link_Table): # pragma: no cover
            self.fail("Registered table is not a Key_Table")
        self.assertEqual(link_table, self.jira.get_table("test_issue_link"))
        self.assertEqual(link_table.name, "test_issue_link")

    def test_properties(self) -> None:
        """
        Test retrieving properties of the collector.
        """

        self.assertEqual(self.jira.project, self.project)
        self.assertEqual(self.jira.project_key, 'TEST')

        self.assertEqual(self.jira.updated_since.timestamp,
                         Update_Tracker.NULL_TIMESTAMP)

        self.assertRegex(self.jira.search_fields, '.+,creator$')

    @patch('gatherer.jira.query.Query', autospec=True)
    def test_search_issues(self, query_class: MagicMock) -> None:
        """
        Test searching for issues in batches.
        """

        query = query_class.return_value
        # Provide batched query return values as side effect iterable.
        attrs = {'perform_batched_query.side_effect': [[self.issue], []]}
        query.configure_mock(**attrs)
        self.jira.search_issues(query)
        self.assertEqual(query.perform_batched_query.call_count, 2)
        query.update.assert_called_once_with()
        self.assertEqual(len(self.jira.get_table("issue")), 1)

    @patch.object(Table, 'write')
    def test_write_tables(self, writer: MagicMock) -> None:
        """
        Test exporting all data to JSON output files.
        """

        self.jira.write_tables()
        writer.assert_called_with(Path('export/TEST'))

    @patch('gatherer.jira.collector.Query', autospec=True)
    @patch.object(Table, 'write')
    @patch.object(Project, 'export_sources')
    def test_process(self, exporter: MagicMock, writer: MagicMock,
                     query_class: MagicMock) -> None:
        """
        Test performing all steps to export the issues.
        """

        query = query_class.return_value
        # Provide batched query return values as side effect iterable.
        query_attrs = {
            'perform_batched_query.side_effect': [[self.issue], []],
            'latest_update': '2024-04-22 11:00:00'
        }
        query.configure_mock(**query_attrs)
        api_project = Mock()
        api_project.configure_mock(name='Test Project')
        api_attrs: Dict[str, Union[str, Dict[str, str], Mock, Type[JIRAError]]] = {
            'JIRA_BASE_URL': JIRA.JIRA_BASE_URL,
            'myself.return_value': {
                'self': 'https://jira.test/rest/agile/version/'
            },
            'project.return_value': api_project
        }
        query.api.configure_mock(**api_attrs)

        jira = Source.from_type('jira', name='JT', url='https://jira.test/')
        if not isinstance(jira, Jira): # pragma: no cover
            self.fail("Invalid source")

        self.assertEqual(self.jira.process(jira, 'test=1'),
                         '2024-04-22 11:00:00')
        query_class.assert_called_once_with(self.jira, jira, 'test=1')

        exporter.assert_called_once_with()

        writer.assert_called_with(Path('export/TEST'))

        jira_source = self.project.sources.find_source_type(Jira)
        if not isinstance(jira_source, Jira): # pragma: no cover
            self.fail("Invalid source")
        self.assertEqual(jira_source.name, 'Test Project')

        # Test replacing source in project sources.
        self.project.sources.clear()
        self.project.sources.add(jira)
        query.configure_mock(**query_attrs)
        self.jira.process(jira)

        self.assertNotIn(jira, self.project.sources)
        jira_source = self.project.sources.find_source_type(Jira)
        if not isinstance(jira_source, Jira): # pragma: no cover
            self.fail("Invalid source")
        self.assertEqual(jira_source.name, 'Test Project')

        # Test handling error when extracting name from project.
        self.project.sources.clear()
        self.project.sources.add(jira)
        api_attrs = {
            'project.side_effect': JIRAError
        }
        query.api.configure_mock(**api_attrs)
        query.configure_mock(**query_attrs)
        self.jira.process(jira)

        self.assertNotIn(jira, self.project.sources)
        jira_source = self.project.sources.find_source_type(Jira)
        if not isinstance(jira_source, Jira): # pragma: no cover
            self.fail("Invalid source")
        self.assertEqual(jira_source.name, 'TEST')

        # Test handling a non-matching URL from myself API endpoint.
        self.project.sources.clear()
        self.project.sources.add(jira)
        api_attrs = {
            'myself.return_value': {
                'self': 'https://redirected.test/jira/rest/agile/'
            }
        }
        query.api.configure_mock(**api_attrs)
        query.configure_mock(**query_attrs)
        self.jira.process(jira)

        # The old source is kept.
        self.assertIn(jira, self.project.sources)
