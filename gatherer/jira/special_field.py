"""
Special field parsers.
"""

from .base import Base_Jira_Field

class Special_Field(Base_Jira_Field):
    """
    A special field with additional data that cannot be parsed in conventional
    ways and is likely stored in a separate table.
    """

    _fields = {}

    @classmethod
    def register(cls, field_name):
        """
        Decorator method for a special parser field class.
        """

        def decorator(subject):
            """
            Decorator that registers the class `subject` to the field name.
            """

            cls._fields[field_name] = subject
            return subject

        return decorator

    @classmethod
    def get_field_class(cls, field_name):
        """
        Retrieve a special field parser class for the given `field_name`.
        """

        return cls._fields[field_name]

    def __init__(self, jira, name, **info):
        self.jira = jira
        self.name = name
        self.info = info

    def parse(self, issue):
        """
        Retrieve the field from an issue and collect relevant data within
        appropriate data storage.
        """

        if hasattr(issue.fields, self.name):
            field = getattr(issue.fields, self.name)
            if field is not None:
                self.collect(issue, field)

        return None

    def collect(self, issue, field):
        """
        Retrieve relevant data from the field belonging to the issue,
        and store the data where appropriate.
        """

        raise NotImplementedError("Subclasses must override this method")

    @property
    def search_field(self):
        return self.name

@Special_Field.register("comment")
class Comment_Field(Special_Field):
    """
    Field parser for the comments of a JIRA issue.
    """

    def collect(self, issue, field):
        if hasattr(field, 'comments'):
            for comment in field.comments:
                row = {}
                for subfield, datatype in self.info["table"].iteritems():
                    if subfield in self.info["fields"]:
                        fieldname = self.info["fields"][subfield]
                    else:
                        fieldname = subfield

                    if hasattr(comment, fieldname):
                        prop = getattr(comment, fieldname)
                        parser = self.jira.get_type_cast(datatype)
                        row[subfield] = parser.parse(prop)
                    else:
                        row[subfield] = str(0)

                row["issue_id"] = str(issue.id)
                self.jira.get_table("comments").append(row)

    @property
    def table_name(self):
        return "comments"

    @property
    def table_key(self):
        return "id"

@Special_Field.register("issuelinks")
class Issue_Link_Field(Special_Field):
    """
    Field parser for the issue links related to an issue.
    """

    def collect(self, issue, field):
        for issuelink in field:
            if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                continue

            self.jira.get_table("relationshiptype").append({
                'id': str(issuelink.type.id),
                'name': str(issuelink.type.name),
                'inward': str(issuelink.type.inward),
                'outward': str(issuelink.type.outward)
            })

            if hasattr(issuelink, 'outwardIssue'):
                self.jira.get_table("issuelinks").append({
                    'from_id': str(issue.id),
                    'to_id': str(issuelink.outwardIssue.id),
                    'relationshiptype': str(issuelink.type.id)
                })

            if hasattr(issuelink, 'inwardIssue'):
                self.jira.get_table("issuelinks").append({
                    'from_id': str(issue.id),
                    'to_id': str(issuelink.inwardIssue.id),
                    'relationshiptype': str(issuelink.type.id)
                })

    @property
    def table_name(self):
        return "issuelinks"

    @property
    def table_key(self):
        return ('from_id', 'to_id', 'relationshiptype')

@Special_Field.register("subtasks")
class Subtask_Field(Special_Field):
    """
    Field parser for the subtasks related to an issue.
    """

    def collect(self, issue, field):
        for subtask in field:
            self.jira.get_table("subtasks").append({
                'from_id': str(issue.id),
                'to_id': str(subtask.id)
            })

    @property
    def table_name(self):
        return "subtasks"

    @property
    def table_key(self):
        return ('from_id', 'to_id')
