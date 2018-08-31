"""
Parsers for VSTS work item fields.
"""

import re
from ..utils import parse_utc_date, parse_unicode

class Field_Parser(object):
    """
    Base parser for VSTS work item fields.
    """

    @property
    def type(self):
        """
        Retrieve the type of data that this parser understands.
        """

        raise NotImplementedError("Must be overridden in subclass")

    def parse(self, value):
        """
        Parse a work item field or revision value.

        Returns the value formatted according to the type.
        """

        raise NotImplementedError("Must be overridden in subclass")

class Table_Parser(Field_Parser):
    """
    Base class for fields that fill in tables.
    """

    def __init__(self, tables):
        if self.table_name not in tables:
            raise KeyError("Cannot find table {}".format(self.table_name))

        self._table = tables[self.table_name]

    @property
    def table_name(self):
        """
        Provide the table name to provide for this parser.
        """

        raise NotImplementedError("Must be overridden in subclass")

class String_Parser(Field_Parser):
    """
    Parser for string fields.
    """

    @property
    def type(self):
        return "string"

    def parse(self, value):
        return str(value)

class Int_Parser(Field_Parser):
    """
    Parser for integer fields.
    """

    @property
    def type(self):
        return "integer"

    def parse(self, value):
        return str(int(value))

class Date_Parser(Field_Parser):
    """
    Parser for timestamp fields.
    """

    @property
    def type(self):
        return "timestamp"

    def parse(self, value):
        return parse_utc_date(value)

class Unicode_Parser(Field_Parser):
    """
    Parser for fields that may include unicode characters.
    """

    @property
    def type(self):
        return "unicode"

    def parse(self, value):
        return parse_unicode(value)

class Decimal_Parser(Field_Parser):
    """
    Parser for numerical fields with possibly a decimal point in them.
    """

    @property
    def type(self):
        return "decimal"

    def parse(self, value):
        return str(float(value))

class Developer_Parser(Table_Parser):
    """
    Parser for fields that contain information about a VSTS user, including
    their display name and email address.
    """

    @property
    def type(self):
        return "developer"

    def parse(self, value):
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
    def table_name(self):
        return "tfs_developer"

class Tags_Parser(Field_Parser):
    """
    Parser for semicolon-and-space separated items in fields.
    """

    @property
    def type(self):
        return "tags"

    def parse(self, value):
        tags = value.split('; ')
        return str(len(tags))
