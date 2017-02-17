"""
Special field parsers.
"""

from .base import Table_Key_Source

class Special_Field(Table_Key_Source):
    """
    A special field with additional data that cannot be parsed in conventional
    ways and is likely stored in a separate table.
    """

    def __init__(self, jira, **info):
        self.jira = jira
        self.info = info

    def parse(self, issue, field):
        """
        Retrieve relevant data from the field belonging to the issue,
        and store the data where appropriate.
        """

        raise NotImplementedError("Subclasses must override this method")

class Comment_Field(Special_Field):
    """
    Field parser for the comments of a JIRA issue.
    """

    def parse(self, issue, field):
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
    def table_key(self):
        return "id"

class Issue_Link_Field(Special_Field):
    """
    Field parser for the issue links related to an issue.
    """

    def parse(self, issue, field):
        for issuelink in field:
            if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                continue

            self.jira.get_table("relationshiptype").append({
                'id': str(issuelink.type.id),
                'name': str(issuelink.type.name),
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
    def table_key(self):
        return ('from_id', 'to_id', 'relationshiptype')

class Subtask_Field(Special_Field):
    """
    Field parser for the subtasks related to an issue.
    """

    def parse(self, issue, field):
        for subtask in field:
            self.jira.get_table("subtasks").append({
                'from_id': str(issue.id),
                'to_id': str(subtask.id)
            })

    @property
    def table_key(self):
        return ('from_id', 'to_id')
