"""
Table structures.
"""

import json
from copy import deepcopy

class Table(object):
    """
    Data storage for eventual JSON output for the database importer.
    """

    def __init__(self, name, filename=None, **kwargs):
        self.name = name
        self.data = []
        self.options = kwargs

        if filename is None:
            self.filename = 'data_{}.json'.format(self.name)
        else:
            self.filename = filename

    def get(self):
        """
        Retrieve a copy of the table data.
        """

        return deepcopy(self.data)

    def append(self, row):
        """
        Insert a row into the table.
        Subclasses may check whether the row already exists and ignore it if
        this is the case.
        """

        self.data.append(row)
        return True

    def extend(self, rows):
        """
        Insert multiple rows at once into the table.
        """

        self.data.extend(rows)

    def write(self, folder):
        """
        Export the table data into a file in the given `folder`.
        """

        with open(folder + "/" + self.filename, 'w') as outfile:
            json.dump(self.data, outfile, indent=4)

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name, key, **kwargs):
        super(Key_Table, self).__init__(name, **kwargs)
        self.key = key
        self.keys = set()

    def append(self, row):
        if row[self.key] in self.keys:
            return False

        self.keys.add(row[self.key])
        return super(Key_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)

class Link_Table(Table):
    """
    Data storage for a table that has a combination of columns that make up
    a primary key.
    """

    def __init__(self, name, link_keys, **kwargs):
        super(Link_Table, self).__init__(name, **kwargs)
        self.link_keys = link_keys
        self.links = set()

    def append(self, row):
        # Link values must be hashable
        link_values = tuple(row[key] for key in self.link_keys)
        if link_values in self.links:
            return False

        self.links.add(link_values)
        super(Link_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)
