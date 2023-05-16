"""
Parsers for VSTS work item fields.

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

import re
from typing import Any, Dict, Optional, Union
from ..table import Table
from ..utils import parse_utc_date, parse_unicode

class Field_Parser:
    """
    Base parser for VSTS work item fields.
    """

    @property
    def type(self) -> str:
        """
        Retrieve the type of data that this parser understands.
        """

        raise NotImplementedError("Must be overridden in subclass")

    def parse(self, value: Any) -> Optional[str]:
        """
        Parse a work item field or revision value.

        Returns the value formatted according to the type, or `None` if it
        could not be parsed.
        """

        raise NotImplementedError("Must be overridden in subclass")

class Table_Parser(Field_Parser):
    """
    Base class for fields that fill in tables.
    """

    def __init__(self, tables: Dict[str, Table]) -> None:
        if self.table_name not in tables:
            raise KeyError(f"Cannot find table {self.table_name}")

        self._table = tables[self.table_name]

    @property
    def table_name(self) -> str:
        """
        Provide the table name to provide for this parser.
        """

        raise NotImplementedError("Must be overridden in subclass")

class String_Parser(Field_Parser):
    """
    Parser for string fields.
    """

    @property
    def type(self) -> str:
        return "string"

    def parse(self, value: str) -> Optional[str]:
        return str(value)

class Int_Parser(Field_Parser):
    """
    Parser for integer fields.
    """

    @property
    def type(self):
        return "integer"

    def parse(self, value: Union[int, str]) -> Optional[str]:
        return str(int(value))

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields.
    """

    @property
    def type(self) -> str:
        return "timestamp"

    def parse(self, value: str) -> Optional[str]:
        return parse_utc_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    @property
    def type(self) -> str:
        return "unicode"

    def parse(self, value: str) -> Optional[str]:
        return parse_unicode(value)

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    @property
    def type(self) -> str:
        return "decimal"

    def parse(self, value: Union[float, str]) -> Optional[str]:
        return str(float(value))

class Developer_Parser(Table_Parser):
    """
    Parser for fields that contain information about a VSTS user, including
    their display name and email address.
    """

    @property
    def type(self) -> str:
        return "developer"

    def parse(self, value: str) -> Optional[str]:
        match = re.match(r"^(.*) <(.*)>$", value)
        if not match:
            return None

        name = parse_unicode(match.group(1))
        email = parse_unicode(match.group(2))
        self._table.append({
            "display_name": name,
            "email": email
        })

        return name

    @property
    def table_name(self) -> str:
        return "tfs_developer"

class Tags_Parser(Field_Parser):
    """
    Parser for semicolon-and-space separated items in fields.
    """

    @property
    def type(self) -> str:
        return "tags"

    def parse(self, value: str) -> Optional[str]:
        tags = value.split('; ')
        return str(len(tags))
