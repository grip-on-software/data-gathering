"""
Tests for parsers of Azure DevOps (previously VSTS and TFS) work item fields.

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

from datetime import datetime, timezone
import unittest
import dateutil.tz
from gatherer.table import Key_Table
from gatherer.vsts.parser import String_Parser, Int_Parser, Date_Parser, \
    Unicode_Parser, Decimal_Parser, Developer_Parser, Tags_Parser

class FieldParserTest(unittest.TestCase):
    """
    Base test class for parser of VSTS work item fields.
    """

class StringParserTest(FieldParserTest):
    """
    Tests for parser of string fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = String_Parser()
        self.assertEqual(parser.parse('foobar'), 'foobar')

class IntParserTest(FieldParserTest):
    """
    Tests for parser of integer fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = Int_Parser()
        self.assertEqual(parser.parse('3'), '3')
        self.assertEqual(parser.parse(4), '4')

class DateParserTest(FieldParserTest):
    """
    Tests for parser of timestamp fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = Date_Parser()
        date = datetime(2024, 5, 1, 14, 17, 5,
                        tzinfo=timezone.utc).astimezone(dateutil.tz.tzlocal())
        self.assertEqual(parser.parse('2024-05-01T14:17:05Z'),
                         date.strftime('%Y-%m-%d %H:%M:%S'))

class UnicodeParserTest(FieldParserTest):
    """
    Tests for parser of fields that may include unicode characters.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = Unicode_Parser()
        self.assertEqual(parser.parse('foo\ud800bar'), 'foo?bar')

class DecimalParserTest(FieldParserTest):
    """
    Tests for parser of numeric fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = Decimal_Parser()
        self.assertEqual(parser.parse('3'), '3.0')
        self.assertEqual(parser.parse('3.5'), '3.5')
        self.assertEqual(parser.parse(4), '4.0')
        self.assertEqual(parser.parse(4.99), '4.99')

class DeveloperParserTest(FieldParserTest):
    """
    Tests for parser of fields that contain information about a user.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        with self.assertRaises(KeyError):
            parser = Developer_Parser({})

        table = Key_Table("tfs_developer", "display_name")
        parser = Developer_Parser({"tfs_developer": table})
        self.assertEqual(parser.parse('testuser <user@foo.test>'), 'testuser')
        self.assertEqual(parser.parse('testuser <user@bar.test>'), 'testuser')
        self.assertEqual(table.get(), [
            {
                'display_name': 'testuser',
                'email': 'user@foo.test'
            }
        ])

        table.clear()
        self.assertIsNone(parser.parse('unknown user format'))
        self.assertEqual(table.get(), [])

class TagsParserTest(FieldParserTest):
    """
    Tests for parser of semicolon-and-space separated items in fields.
    """

    def test_parse(self) -> None:
        """
        Test parsing a work item field.
        """

        parser = Tags_Parser()
        self.assertEqual(parser.parse('foo; bar; baz'), '3')
        self.assertEqual(parser.parse('other'), '1')
        self.assertEqual(parser.parse(''), '0')
