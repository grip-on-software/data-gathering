"""
Field definitions that fetch fields from JIRA API issue results.
"""

from builtins import str
from .base import Base_Jira_Field, Base_Changelog_Field

###
# Field definitions
###

class Jira_Field(Base_Jira_Field):
    """
    Field parser for the issue field data returned by the JIRA REST API.
    """

    def __init__(self, jira, name, **data):
        self.jira = jira
        self.name = name
        self.data = data

    def fetch(self, issue):
        """
        Retrieve the raw data from the issue.

        This method is responsible for determining the correct field to use, and
        to preprocess it as much as possible (such as extracting an ID from its
        subproperties). The returned value is not yet parsed according to the
        type of the field.
        """

        raise NotImplementedError("Subclasses must extend this method")

    def parse(self, issue):
        """
        Retrieve the field from the issue and parse it so that it receives the
        correct type and format.
        """

        field = self.fetch(issue)
        return self.cast(field)

    def cast(self, field):
        """
        Use the appropriate type cast to convert the fetched field to a string
        representation of the field.
        """

        if field is None:
            return str(0)

        for parser in self.get_types():
            field = parser.parse(field)

        return field

    def get_types(self):
        """
        Retrieve the type parsers that this field uses in sequence to perform
        its type casting actions.
        """

        if "type" in self.data:
            if isinstance(self.data["type"], list):
                types = self.data["type"]
            else:
                types = (self.data["type"],)

            return [self.jira.get_type_cast(datatype) for datatype in types]

        return []

    @property
    def table_name(self):
        # If this field wishes to have a table, then default to the field name.
        # Jira.register_table overrides this with the table name provided in
        # the field specification data if possible.
        if "table" in self.data:
            return self.name
        else:
            return None

class Primary_Field(Jira_Field):
    """
    A field in the JIRA response that contains primary information of the issue,
    such as the ID or key of the issue.
    """

    def fetch(self, issue):
        return getattr(issue, self.data["primary"])

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Primary field '" + self.name + "' is not keyable at this moment")

class Payload_Field(Jira_Field):
    """
    A field in the JIRA's main payload response, which are the editable fields
    as well as metadata fields for the issue.
    """

    def fetch(self, issue):
        if hasattr(issue.fields, self.data["field"]):
            return getattr(issue.fields, self.data["field"])

        return None

    @property
    def search_field(self):
        return self.data["field"]

    @property
    def table_key(self):
        return "id"

class Property_Field(Payload_Field):
    """
    A field in the JIRA's main payload response of which one property is the
    identifying value for that field in the issue.
    """

    def fetch(self, issue):
        field = super(Property_Field, self).fetch(issue)
        if hasattr(field, self.data["property"]):
            return getattr(field, self.data["property"])

        return None

    def parse(self, issue):
        field = super(Property_Field, self).parse(issue)
        if field is None:
            return None

        if "table" in self.data and isinstance(self.data["table"], dict):
            payload_field = super(Property_Field, self).fetch(issue)
            row = {self.data["property"]: field}
            has_data = False
            for name, datatype in self.data["table"].items():
                if hasattr(payload_field, name):
                    has_data = True
                    prop = getattr(payload_field, name)
                    row[name] = self.jira.get_type_cast(datatype).parse(prop)
                else:
                    row[name] = str(0)

            if has_data:
                self.jira.get_table(self.name).append(row)

        return field

    @property
    def table_key(self):
        return self.data["property"]

class Changelog_Primary_Field(Jira_Field, Base_Changelog_Field):
    """
    A field in the change items in the changelog of the JIRA response.
    """

    def fetch(self, entry):
        if hasattr(entry, self.data["changelog_primary"]):
            return getattr(entry, self.data["changelog_primary"])

        return None

    def parse_changelog(self, entry, diffs, issue):
        return self.parse(entry)

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Changelog fields are not keyable at this moment")

class Changelog_Field(Jira_Field, Base_Changelog_Field):
    """
    A field in the changelog items of the JIRA expanded response.
    """

    def fetch(self, issue):
        data = issue.__dict__
        if data['from'] is not None:
            return data['from']
        if data['fromString'] is not None:
            return data['fromString']

        return None

    def parse_changelog(self, entry, diffs, issue):
        """
        Parse changelog information from a changelog entry.
        """

        field = self.parse(entry)
        for parser in self.get_types():
            field = parser.parse_changelog(entry.__dict__, field, diffs)

        return field

    @property
    def search_field(self):
        return None

    @property
    def table_key(self):
        raise Exception("Changelog fields are not keyable at this moment")
