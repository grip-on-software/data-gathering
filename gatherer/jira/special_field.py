"""
Special field parsers.
"""

from datetime import datetime
import logging
from .base import Base_Jira_Field, Base_Changelog_Field

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
                is_newer = False
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

                    if datatype == 'date' and self.jira.updated_since.is_newer(row[subfield]):
                        is_newer = True

                row["issue_id"] = str(issue.id)
                if is_newer:
                    self.jira.get_table("comments").append(row)

    @property
    def table_name(self):
        return "comments"

    @property
    def table_key(self):
        return "id"

@Special_Field.register("issuelinks")
class Issue_Link_Field(Special_Field, Base_Changelog_Field):
    """
    Field parser for the issue links related to an issue.
    """

    _changelog_map = {
        'to': 'start_date',
        'from': 'end_date'
    }

    def __init__(self, jira, name, **info):
        super(Issue_Link_Field, self).__init__(jira, name, **info)
        self._relations = {}
        self.jira.register_prefetcher(self.prefetch)

    def prefetch(self, query):
        """
        Retrieve all relationship types from the query API.
        """

        relationships = query.api.issue_link_types()
        table = self.jira.get_table("relationshiptype")
        for relationship in relationships:
            relation_id = str(relationship.id)
            inward = str(relationship.inward)
            outward = str(relationship.outward)
            self._relations[inward] = {
                'id': relation_id,
                'outward': str(-1)
            }
            self._relations[outward] = {
                'id': relation_id,
                'outward': str(1)
            }
            table.append({
                'id': relation_id,
                'name': str(relationship.name),
                'inward': inward,
                'outward': outward
            })

    def collect(self, issue, field):
        for issuelink in field:
            if not hasattr(issuelink, 'type') or not hasattr(issuelink.type, 'id'):
                continue


            self._check_link(issue, issuelink, outward=True)
            self._check_link(issue, issuelink, outward=False)

    def _check_link(self, issue, issuelink, outward=True):
        if outward:
            attr = 'outwardIssue'
            direction = str(1)
        else:
            attr = 'inwardIssue'
            direction = str(-1)

        if hasattr(issuelink, attr):
            prop = getattr(issuelink, attr)
            from_key = str(issue.key)
            to_key = str(prop.key)
            self.jira.get_table("issuelinks").append({
                'from_key': from_key,
                'to_key': to_key,
                'relationshiptype': str(issuelink.type.id),
                'outward': direction,
                'start_date': str(0),
                'end_date': str(0)
            })

    def parse_changelog(self, entry, diffs, issue):
        from_key = str(issue.key)
        data = entry.__dict__
        self._check_changelog(data, diffs, from_key, 'to')
        self._check_changelog(data, diffs, from_key, 'from')

        return None

    def _check_changelog(self, data, diffs, from_key, entry_field):
        if data[entry_field] is None:
            return

        text = data['{}String'.format(entry_field)]
        table = self.jira.get_table("issuelinks")
        search_row = {
            'from_key': from_key,
            'to_key': str(data[entry_field])
        }
        match_row = {}
        row = None
        for relation, candidate in self._relations.iteritems():
            if relation in text:
                # Find a row with this relation. We only stop if we find such
                # a row, because we might have relations with conflicting
                # (similar) inward/outward names. This way, we check for other
                # relations if we did not add a row from another change or the
                # payload field, which is likely to happen for exact matches.
                match_row = search_row.copy()
                match_row.update({
                    'relationshiptype': candidate['id'],
                    'outward': candidate['outward']
                })
                row = table.get_row(match_row)
                if row is not None:
                    break

        if not match_row:
            # Cannot deduce relation
            logging.warning('Cannot deduce relation from changelog: %s', text)
            return

        update_field = self._changelog_map[entry_field]
        if row is None:
            # Create a new row.
            match_row.update({
                'start_date': str(0),
                'end_date': str(0)
            })
            match_row[update_field] = diffs["updated"]
            table.append(match_row)
            return

        if row[update_field] != str(0):
            # Links may be added and removed multiple times; we keep the
            # earliest start date and latest end date of the link.
            older = datetime.strptime(diffs["updated"], '%Y-%m-%d %H:%M:%S') < \
                    datetime.strptime(row[update_field], '%Y-%m-%d %H:%M:%S')
            if older and update_field == 'end_date':
                logging.info('Older link end date in %s: %s, %s', from_key,
                             diffs["updated"], row[update_field])
                return
            elif not older and update_field == 'start_date':
                logging.info('Newer link start date in %s: %s, %s', from_key,
                             diffs["updated"], row[update_field])
                return

        table.update(match_row, {update_field: diffs["updated"]})

    @property
    def table_name(self):
        return "issuelinks"

    @property
    def table_key(self):
        return ('from_key', 'to_key', 'relationshiptype', 'outward')

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
