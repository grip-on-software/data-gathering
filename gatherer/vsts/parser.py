"""
Parsers for VSTS work item fields.
"""

import re
from typing import Any, Dict, Union
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

    def parse(self, value: Any) -> str:
        """
        Parse a work item field or revision value.

        Returns the value formatted according to the type.
        """

        raise NotImplementedError("Must be overridden in subclass")

class Table_Parser(Field_Parser):
    """
    Base class for fields that fill in tables.
    """

    def __init__(self, tables: Dict[str, Table]) -> None:
        if self.table_name not in tables:
            raise KeyError("Cannot find table {}".format(self.table_name))

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

    def parse(self, value: str) -> str:
        return str(value)

class Int_Parser(Field_Parser):
    """
    Parser for integer fields.
    """

    @property
    def type(self):
        return "integer"

    def parse(self, value: Union[int, str]) -> str:
        return str(int(value))

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields.
    """

    @property
    def type(self) -> str:
        return "timestamp"

    def parse(self, value: str) -> str:
        return parse_utc_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    @property
    def type(self) -> str:
        return "unicode"

    def parse(self, value: str) -> str:
        return parse_unicode(value)

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    @property
    def type(self) -> str:
        return "decimal"

    def parse(self, value: Union[float, str]) -> str:
        return str(float(value))

class Developer_Parser(Table_Parser):
    """
    Parser for fields that contain information about a VSTS user, including
    their display name and email address.
    """

    @property
    def type(self) -> str:
        return "developer"

    def parse(self, value: str) -> str:
        match = re.match(r"^(.*) <(.*)>$", value)
        if not match:
            return ""

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

    def parse(self, value: str) -> str:
        tags = value.split('; ')
        return str(len(tags))
