"""
Tests for module that defines fields for JIRA API issue results.

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

import unittest
from unittest.mock import Mock
from jira.resources import Issue
from jira.resilientsession import ResilientSession
from gatherer.domain.project import Project
from gatherer.jira.base import TableKeyError
from gatherer.jira.changelog import ChangeHistory, ChangeItem
from gatherer.jira.collector import Collector, Field
from gatherer.jira.field import Primary_Field, Payload_Field, \
    Property_Field, Changelog_Primary_Field, Changelog_Item_Field
from gatherer.table import Table

class PrimaryFieldTest(unittest.TestCase):
    """
    Tests for field in the JIRA response that contains primary information of
    the issue.
    """

    def setUp(self) -> None:
        self.jira = Collector(Project('TEST'))
        self.field = Primary_Field(self.jira, 'test', primary='info')
        self.issue = Issue({}, ResilientSession(), {
            'info': 'primary_info_value'
        })

    def test_fetch_parse(self) -> None:
        """
        Test retrieving the raw data from the issue as well as parsing it.
        """

        self.assertEqual(self.field.fetch(self.issue), 'primary_info_value')
        self.assertEqual(self.field.parse(self.issue), 'primary_info_value')

    def test_properties(self) -> None:
        """
        Test properties of the issue field.
        """

        self.assertIsNone(self.field.table_name)
        self.assertIsNone(self.field.search_field)
        with self.assertRaises(TableKeyError):
            self.assertIsNone(self.field.table_key)

class PayloadFieldTest(unittest.TestCase):
    """
    Tests for field in the JIRA main payload response.
    """

    def setUp(self) -> None:
        self.jira = Collector(Project('TEST'))
        self.field = Payload_Field(self.jira, 'test', field='key',
                                   type='str', table={})
        self.issue = Issue({}, ResilientSession(), {
            'fields': {
                'key': 'payload'
            }
        })

    def test_fetch_parse(self) -> None:
        """
        Test retrieving the raw data from the issue as well as parsing it.
        """

        self.assertEqual(self.field.fetch(self.issue), 'payload')
        self.assertEqual(self.field.parse(self.issue), 'payload')

    def test_properties(self) -> None:
        """
        Test properties of the issue field.
        """

        self.assertEqual(self.field.table_name, 'test')
        self.assertEqual(self.field.search_field, 'key')
        self.assertEqual(self.field.table_key, 'id')

class PropertyFieldTest(unittest.TestCase):
    """
    Tests for field in the JIRA main payload response with a propery identifying
    the value for that field.
    """

    def setUp(self) -> None:
        self.jira = Collector(Project('TEST'))
        self.data: Field = {
            'field': 'head',
            'property': 'sub',
            'type': 'str',
            'table': {
                'count': 'int',
                'optional': 'str',
                'extra': 'unicode'
            }
        }
        self.field = Property_Field(self.jira, 'test', **self.data)

    def test_fetch_parse(self) -> None:
        """
        Test retrieving the raw data from the issue as well as parsing it.
        """

        table = self.jira.register_table(self.data, self.field)
        if not isinstance(table, Table): # pragma: no cover
            self.fail('Invalid table')
        self.assertEqual(table.name, 'test')
        session = ResilientSession()
        full_issue = Issue({}, session, {
            'fields': {
                'head': {
                    'sub': 'prop',
                    'count': '123',
                    'optional': None
                },
                'start': {'nest': 'bla'}
            }
        })
        self.assertEqual(self.field.fetch(full_issue), 'prop')
        self.assertEqual(self.field.parse(full_issue), 'prop')
        self.assertEqual(table.get(), [
            {
                'sub': 'prop',
                'count': '123',
                'optional': '0',
                'extra': '0'
            }
        ])

        empty_issue = Issue({}, session, {
            'fields': {'other': '1'}
        })
        self.assertIsNone(self.field.fetch(empty_issue))
        self.assertIsNone(self.field.parse(empty_issue))
        self.assertEqual(len(table), 1)

        partial_issue = Issue({}, session, {
            'fields': {
                'head': {
                    'sub': 'something'
                }
            }
        })
        self.assertEqual(self.field.fetch(partial_issue), 'something')
        self.assertEqual(self.field.parse(partial_issue), 'something')
        self.assertEqual(len(table), 1)

        data: Field = {
            'field': 'start',
            'property': 'nest',
            'type': 'str'
        }
        tableless = Property_Field(self.jira, 'tableless', **data)
        self.assertIsNone(self.jira.register_table(data, tableless))
        self.assertEqual(tableless.fetch(full_issue), 'bla')
        self.assertEqual(tableless.parse(full_issue), 'bla')

    def test_properties(self) -> None:
        """
        Test properties of the issue field.
        """

        self.assertEqual(self.field.table_name, 'test')
        self.assertEqual(self.field.search_field, 'head')
        self.assertEqual(self.field.table_key, 'sub')

class ChangelogPrimaryFieldTest(unittest.TestCase):
    """
    Tests for field in the change entry in the changelog of the JIRA response.
    """

    def setUp(self) -> None:
        self.jira = Collector(Project('TEST'))
        self.field = Changelog_Primary_Field(self.jira, 'test',
                                             changelog_primary='id',
                                             type='int')
        self.entry = ChangeHistory({}, ResilientSession(), {
            'id': '99'
        })

    def test_fetch(self) -> None:
        """
        Test retrieving the raw data from the changelog history entry.
        """

        self.assertEqual(self.field.fetch(self.entry, None), '99')

    def test_parse_changelog(self) -> None:
        """
        Test parsing changelog information from a changelog entry.
        """

        issue = Issue({}, ResilientSession(), {})
        self.assertEqual(self.field.parse_changelog(self.entry, {}, issue, None),
                         '99')

    def test_properties(self) -> None:
        """
        Test properties of the issue changelog field.
        """

        self.assertIsNone(self.field.table_name)
        self.assertIsNone(self.field.search_field)
        with self.assertRaises(TableKeyError):
            self.assertIsNone(self.field.table_key)

class ChangelogItemFieldTest(unittest.TestCase):
    """
    Tests for field in the changelog items of the JIRA expanded response.
    """

    def setUp(self) -> None:
        self.jira = Collector(Project('TEST'))
        self.field = Changelog_Item_Field(self.jira, 'test')

        attrs = {
            'from': 'old',
            'fromString': 'Old version',
            'to': 'new',
            'toString': 'New version'
        }
        self.item = Mock(**attrs, spec=ChangeItem)

    def test_fetch(self) -> None:
        """
        Test retrieving the raw data from the changelog history entry.
        """

        entry = ChangeHistory({}, ResilientSession(), {})
        self.assertIsNone(self.field.fetch(entry, None))
        self.assertEqual(self.field.fetch(entry, self.item), 'old')

        attrs = {'from': None}
        self.item.configure_mock(**attrs)
        self.assertEqual(self.field.fetch(entry, self.item), 'Old version')

        attrs = {'from': None, 'fromString': None}
        self.item.configure_mock(**attrs)
        self.assertIsNone(self.field.fetch(entry, self.item))

    def test_parse_changelog(self) -> None:
        """
        Test parsing changelog information from a changelog entry.
        """

        session = ResilientSession()
        entry = ChangeHistory({}, session, {})
        issue = Issue({}, session, {})
        self.assertIsNone(self.field.parse_changelog(entry, {}, issue, None))
        self.assertEqual(self.field.parse_changelog(entry, {}, issue,
                                                    self.item), 'old')
