"""
Table structures.
"""

from builtins import object, str
import json
import os
import re
from copy import copy, deepcopy
from .salt import Salt

class Table(object):
    """
    Data storage for eventual JSON output for the database importer.
    """

    def __init__(self, name, filename=None, merge_update=False,
                 encrypt_fields=None):
        self._name = name
        self._data = []
        self._merge_update = merge_update
        self._encrypt_fields = encrypt_fields

        if self._encrypt_fields is not None and os.path.exists("secrets.json"):
            with open("secrets.json") as secrets_file:
                self._secrets = json.load(secrets_file)
        else:
            self._secrets = None

        if filename is None:
            self._filename = 'data_{}.json'.format(self._name)
        else:
            self._filename = filename

    @property
    def name(self):
        """
        Retrieve the name of the table.
        """

        return self._name

    def _convert_username(self, username):
        for search_set in self._secrets['usernames']:
            if 'pattern' in search_set:
                pattern = search_set['pattern']
                replace = search_set['replace'].replace('$', '\\')
            else:
                pattern = re.escape(search_set['prefix'])
                replace = ''

            if re.match(pattern, username):
                username = re.sub(pattern, replace, username)
                if 'mutate' in search_set and search_set['mutate'] == 'lower':
                    username = username.lower()

                return username

        return username

    def _encrypt(self, row):
        if self._encrypt_fields is None:
            return row

        if self._secrets is None:
            row["encrypted"] = str(0)
            return row

        if "encrypted" in row and row["encrypted"] != str(0):
            return row

        salt = str(self._secrets['salts']['salt']).encode('utf-8')
        pepper = str(self._secrets['salts']['pepper']).encode('utf-8')

        for field in self._encrypt_fields:
            if 'usernames' in self._secrets and field.endswith('username'):
                row[field] = self._convert_username(row[field])

            if row[field] != str(0):
                row[field] = Salt.encrypt(row[field].encode('utf-8'), salt, pepper)

        row["encrypted"] = str(1)
        return row

    def get(self):
        """
        Retrieve a copy of the table data.
        """

        return deepcopy(self._data)

    def has(self, row):
        """
        Check whether the `row` (or an identifier contained within) already
        exists within the table.

        The default Table implementation uses a slow linear comparison, but
        subclasses may override this with other comparisons and searches using
        identifiers in the row.
        """

        return self._encrypt(row) in self._data

    def _fetch_row(self, row):
        """
        Retrieve a row from the table, and return it without copying.

        Raises a `ValueError` or `KeyError` if the row does not exist.
        """

        # Actually get the real row so that values that compare equal between
        # the given row and our row are replaced.
        index = self._data.index(self._encrypt(row))
        return self._data[index]

    def get_row(self, row):
        """
        Retrieve a row from the table.

        The given `row` is searched for in the table, using the row fields
        (or the fields that make up an identifier). If the row is found, then
        a copy of the stored row is returned, otherwise `None` is returned.

        The default implementation provides no added benefit compared to `has`,
        but subclasses may override this to perform row searches using
        identifiers.
        """

        try:
            return copy(self._fetch_row(row))
        except (KeyError, ValueError):
            return None

    def append(self, row):
        """
        Insert a row into the table.
        Subclasses may check whether the row (or some identifier in it) already
        exists in the table, and ignore it if this is the case.
        The return value indicates whether the row is newly added to the table.
        """

        self._data.append(self._encrypt(row))
        return True

    def extend(self, rows):
        """
        Insert multiple rows at once into the table.
        """

        self._data.extend([self._encrypt(row) for row in rows])

    def update(self, search_row, update_row):
        """
        Search for a given row `search_row` in the table, and update the fields
        in it using `update_row`.

        If the row cannot be found using the `search_row` argument, then this
        method raises a `ValueError` or `KeyError`. Note that subclasses that
        impose unique identifiers may simplify the search by allowing incomplete
        rows where the only the identifying fields are provided. However, such
        subclasses may also raise a `KeyError` if identifiers are provided in
        `update_row` and the subclass does not support changing identifiers.
        """

        row = self._fetch_row(search_row)
        row.update(update_row)

    def write(self, folder):
        """
        Export the table data into a file in the given `folder`.
        """

        if self._merge_update:
            self.load(folder)

        with open(folder + "/" + self._filename, 'w') as outfile:
            json.dump(self._data, outfile, indent=4)

    def load(self, folder):
        """
        Read the table data from the exported file in the given `folder`.

        If the file does not exist, then nothing happens. Otherwise, the data
        is appended to the in-memory table, i.e., it does not overwrite data
        already in memory. More specifically, key tables whose keys conflict
        will prefer the data in memory over the data loaded by this method.
        """

        path = folder + "/" + self._filename
        if os.path.exists(path):
            with open(path, 'r') as infile:
                self.extend(json.load(infile))

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name, key, **kwargs):
        super(Key_Table, self).__init__(name, **kwargs)
        self._key = key
        self._keys = {}

    def has(self, row):
        return row[self._key] in self._keys

    def _fetch_row(self, row):
        key = row[self._key]
        return self._keys[key]

    def append(self, row):
        if self.has(row):
            return False

        key = row[self._key]
        self._keys[key] = row
        return super(Key_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)

    def update(self, search_row, update_row):
        if self._key in update_row:
            raise KeyError('Key {} may not be provided in update row'.format(self._key))

        super(Key_Table, self).update(search_row, update_row)

class Link_Table(Table):
    """
    Data storage for a table that has a combination of columns that make up
    a primary key.
    """

    def __init__(self, name, link_keys, **kwargs):
        super(Link_Table, self).__init__(name, **kwargs)
        self._link_keys = link_keys
        self._links = {}

    def _build_key(self, row):
        # Link values used in the key must be hashable
        return tuple(row[key] for key in self._link_keys)

    def has(self, row):
        return self._build_key(row) in self._links

    def _fetch_row(self, row):
        key = self._build_key(row)
        return self._links[key]

    def append(self, row):
        link_values = self._build_key(row)
        if link_values in self._links:
            return False

        self._links[link_values] = row
        return super(Link_Table, self).append(row)

    def extend(self, rows):
        for row in rows:
            self.append(row)

    def update(self, search_row, update_row):
        disallowed_keys = set(self._link_keys).intersection(update_row.keys())
        if disallowed_keys:
            key_text = 'Key' if len(disallowed_keys) == 1 else 'Keys'
            disallowed = ', '.join(disallowed_keys)
            raise KeyError('{} {} may not be provided in update row'.format(key_text, disallowed))

        super(Link_Table, self).update(search_row, update_row)
