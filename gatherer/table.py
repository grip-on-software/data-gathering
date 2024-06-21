"""
Table structures.

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

import json
import os
from pathlib import Path
import re
from typing import cast, Collection, Dict, Iterator, List, Optional, Sequence, \
    Tuple, Union, TYPE_CHECKING
from copy import copy, deepcopy
from .salt import Salt

Secrets = Dict[str, Union[Dict[str, str], List[Dict[str, str]]]]
Value = str
Row = Dict[str, Value]
if TYPE_CHECKING:
    PathLike = Union[str, os.PathLike[str]]
else:
    PathLike = Union[str, os.PathLike]

class Table(Collection[Row]):
    """
    Data storage for eventual JSON output for the database importer.

    When the gatherer modules are used by a data gathering agent, a file named
    `secrets.json` may be available with username adjustments patterns and
    encryption keys. These are then used by to perform early encryption so that
    the data is made pseudonymous before it leaves the agent's environment.
    """

    def __init__(self, name: str, filename: Optional[str] = None,
                 merge_update: bool = False,
                 encrypt_fields: Optional[Sequence[str]] = None) -> None:
        self._name = name
        self._merge_update = merge_update
        self._encrypt_fields = encrypt_fields

        secrets_path = Path('secrets.json')
        self._secrets: Optional[Secrets] = None
        if self._encrypt_fields is not None and secrets_path.exists():
            with secrets_path.open('r', encoding='utf-8') as secrets_file:
                self._secrets = json.load(secrets_file)

        if filename is None:
            self._filename = f'data_{self._name}.json'
        else:
            self._filename = filename

        self.clear()

    @property
    def name(self) -> str:
        """
        Retrieve the name of the table.
        """

        return self._name

    @property
    def filename(self) -> str:
        """
        Retrieve the filename which is used for loading and exporting the table.
        """

        return self._filename

    @staticmethod
    def _convert_username(usernames: List[Dict[str, str]], username: str) -> str:
        for search_set in usernames:
            pattern = re.escape(search_set['prefix']).replace('%', '.*') \
                .replace('_', '.')
            replace = ''

            if re.match(pattern, username):
                if 'pattern' in search_set:
                    pattern = search_set['pattern']
                    replace = search_set.get('replace', '').replace('$', '\\')

                username = re.sub(pattern, replace, username)
                if search_set.get('mutate') == 'lower':
                    username = username.lower()

                return username

        return username

    def _encrypt(self, row: Row) -> Row:
        # Make a copy so the originally passed dict remains the same.
        row = row.copy()

        if self._encrypt_fields is None:
            return row

        if "encrypted" in row and row["encrypted"] != str(0):
            return row

        if self._secrets is None:
            row["encrypted"] = str(0)
            return row

        salts = cast(Dict[str, str], self._secrets['salts'])
        salt = salts['salt'].encode('utf-8')
        pepper = salts['pepper'].encode('utf-8')
        usernames = self._secrets.get('usernames')

        for field in self._encrypt_fields:
            if field not in row:
                # Sparse tables may not contain every row
                continue

            if isinstance(usernames, list) and field.endswith('username'):
                row[field] = self._convert_username(usernames, row[field])

            if row[field] != str(0):
                row[field] = Salt.encrypt(row[field].encode('utf-8'), salt, pepper)

        row["encrypted"] = str(1)
        return row

    def get(self) -> List[Row]:
        """
        Retrieve a copy of the table data.
        """

        return deepcopy(self._data)

    def has(self, row: Row) -> bool:
        """
        Check whether the `row` (or a unique identifier contained within)
        already exists within the table.

        The default `Table` implementation uses a slow linear comparison, but
        subclasses may override this with other comparisons and searches using
        identifiers in the row.
        """

        return self._encrypt(row) in self._data

    def _fetch_row(self, row: Row) -> Row:
        """
        Retrieve a row from the table, and return it without copying.

        Raises a `ValueError` or `KeyError` if the row does not exist.
        """

        # Actually get the real row so that values that compare equal between
        # the given row and our row are replaced.
        index = self._data.index(self._encrypt(row))
        return self._data[index]

    def get_row(self, row: Row) -> Optional[Row]:
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

    def append(self, row: Row) -> Optional[Row]:
        """
        Insert a row into the table.

        Subclasses may check whether the row (or some identifier in it) already
        exists in the table, and ignore it if this is the case.

        Returns the newly added row or `None` if the row is not added.
        """

        row = self._encrypt(row)
        self._data.append(row)
        return row

    def extend(self, rows: Sequence[Row]) -> Sequence[Optional[Row]]:
        """
        Insert multiple rows at once into the table.

        Subclasses may filter out rows (e.g. based on identifiers in them) which
        already exist in the table.

        Returns a list of the inserted rows, with rows replaced by `None` if
        they were not added.
        """

        extension = [self._encrypt(row) for row in rows]
        self._data.extend(extension)
        return extension

    def update(self, search_row: Row, update_row: Row) -> None:
        """
        Search for a given row `search_row` in the table, and update the fields
        in it using `update_row`.

        If the row cannot be found using the `search_row` argument, then this
        method raises a `ValueError` or `KeyError`. Note that subclasses that
        impose unique identifiers may simplify the search by allowing incomplete
        rows where the only the identifying fields are provided. However, such
        subclasses may also raise a `KeyError` or `ValueError` if (inconsistent)
        identifiers are provided in `update_row` and the subclass does not
        support changing identifiers.
        """

        row = self._fetch_row(search_row)
        row.update(self._encrypt(update_row))

    def write(self, folder: PathLike) -> None:
        """
        Export the table data into a file in the given `folder`.
        """

        if self._merge_update:
            self.load(folder)

        path = Path(folder, self._filename)
        with path.open('w', encoding='utf-8') as outfile:
            json.dump(self._data, outfile, indent=4)

    def load(self, folder: PathLike) -> None:
        """
        Read the table data from the exported file in the given `folder`.

        If the file does not exist, then nothing happens. Otherwise, the data
        is appended to the in-memory table, i.e., it does not overwrite data
        already in memory. More specifically, key tables whose keys conflict
        will prefer the data in memory over the data loaded by this method.
        """

        path = Path(folder, self._filename)
        if path.exists():
            with path.open('r', encoding='utf-8') as infile:
                self.extend(json.load(infile))

    def clear(self) -> None:
        """
        Remove all rows from the table.
        """

        self._data: List[Row] = []

    def __contains__(self, row: object) -> bool:
        if not isinstance(row, dict):
            return False

        return self.has(row)

    def __iter__(self) -> Iterator[Row]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name: str, key: str, filename: Optional[str] = None,
                 merge_update: bool = False,
                 encrypt_fields: Optional[Sequence[str]] = None) -> None:
        super().__init__(name, filename=filename, merge_update=merge_update,
                         encrypt_fields=encrypt_fields)
        self._key = key

    def clear(self) -> None:
        super().clear()
        self._keys: Dict[str, Row] = {}

    def has(self, row: Row) -> bool:
        if self._key not in row:
            return False

        return row[self._key] in self._keys

    def _fetch_row(self, row: Row) -> Row:
        # If the key is both an encryption field and a username, then we may be
        # given an intermediate value, so encrypt the row and fetch based on
        # the encrypted key
        if self._key.endswith('username') and self._secrets is not None and \
            self._encrypt_fields is not None and \
            self._key in self._encrypt_fields:
            row = self._encrypt(row)

        key = row[self._key]
        return self._keys[key]

    def append(self, row: Row) -> Optional[Row]:
        if self.has(row):
            return None

        new_row = super().append(row)
        if new_row is None: # pragma: no cover
            raise ValueError('Unexpected missing row from parent Table')

        # If the key is an encryption field, then store both unencrypted and
        # encrypted keys for lookups
        self._keys[row[self._key]] = new_row
        self._keys[new_row[self._key]] = new_row

        return new_row

    def extend(self, rows: Sequence[Row]) -> Sequence[Optional[Row]]:
        return [self.append(row) for row in rows]

    def update(self, search_row: Row, update_row: Row) -> None:
        key = search_row[self._key]
        if update_row.get(self._key, key) != key:
            raise ValueError(f'Key {self._key} must be same in both search and '
                             f'update row: {key} != {update_row[self._key]}')

        super().update(search_row, update_row)

    def __getitem__(self, key: object) -> Row:
        if not isinstance(key, str):
            raise TypeError('Key_Table[key] is only subscriptable with string '
                            f"keys, not '{type(key)}'")

        return self._keys[key]

    def __setitem__(self, key: object, value: object) -> None:
        if not isinstance(key, str):
            raise TypeError('Key_Table[key] is only subscriptable with string '
                            f'keys, not {type(key)}')
        if not isinstance(value, dict):
            raise TypeError('Key_Table[key] = value is only assignable with '
                            f'row dictionaries, not {type(value)}')

        search_row: Row = {self._key: key}
        try:
            self.update(search_row, value)
        except KeyError:
            search_row.update(value)
            self.append(search_row)

class Link_Table(Table):
    """
    Data storage for a table that has a combination of columns that make up
    a primary key.
    """

    def __init__(self, name: str, link_keys: Sequence[str],
                 filename: Optional[str] = None, merge_update: bool = False,
                 encrypt_fields: Optional[Sequence[str]] = None) -> None:
        super().__init__(name, filename=filename, merge_update=merge_update,
                         encrypt_fields=encrypt_fields)
        self._link_keys = link_keys
        if self._encrypt_fields is None or self._secrets is None:
            self._encrypt_link = False
            self._link_username = False
        else:
            self._encrypt_link = not set(link_keys).isdisjoint(self._encrypt_fields)
            self._link_username = any(key.endswith('username') and
                                      key in self._encrypt_fields
                                      for key in link_keys)

    def clear(self) -> None:
        super().clear()
        self._links: Dict[Tuple[str, ...], Row] = {}

    def _build_key(self, row: Row) -> Tuple[str, ...]:
        # Link values used in the key must be hashable
        return tuple(row[key] for key in self._link_keys)

    def has(self, row: Row) -> bool:
        try:
            link = self._build_key(row)
        except KeyError:
            return False

        return link in self._links

    def _fetch_row(self, row: Row) -> Row:
        # If one of the keys is both an encryption field and a username, then
        # we may be given an intermediate value, so encrypt the row and fetch
        # based on the encrypted key
        if self._link_username:
            row = self._encrypt(row)

        key = self._build_key(row)
        return self._links[key]

    def append(self, row: Row) -> Optional[Row]:
        link_values = self._build_key(row)
        if link_values in self._links:
            return None

        new_row = super().append(row)
        if new_row is None: # pragma: no cover
            raise ValueError('Unexpected missing row from parent Table')

        self._links[link_values] = new_row

        # If the key is an encryption field, then store both unencrypted and
        # encrypted keys for lookups
        if self._encrypt_link:
            self._links[self._build_key(new_row)] = new_row

        return new_row

    def extend(self, rows: Sequence[Row]) -> Sequence[Optional[Row]]:
        return [self.append(row) for row in rows]

    def update(self, search_row: Row, update_row: Row) -> None:
        disallowed_keys: List[str] = []
        for key in self._link_keys:
            if update_row.get(key, search_row[key]) != search_row[key]:
                disallowed_keys.append(key)
        if disallowed_keys:
            key_text = 'Key' if len(disallowed_keys) == 1 else 'Keys'
            disallowed = ', '.join(disallowed_keys)
            search = ', '.join(repr(search_row[key]) for key in disallowed_keys)
            update = ', '.join(repr(update_row.get(key, search_row[key]))
                               for key in disallowed_keys)
            raise ValueError(f'{key_text} {disallowed} must be same in both '
                             f'search and update row: {search} != {update}')

        super().update(search_row, update_row)

    def __getitem__(self, key: object) -> Row:
        if not isinstance(key, tuple):
            raise TypeError('Link_Table[key] is only subscriptable with tuple '
                            f'keys, not {type(key)}')

        return self._links[key]

    def __setitem__(self, key: object, value: object) -> None:
        if not isinstance(key, tuple):
            raise TypeError('Link_Table[key] is only subscriptable with tuple '
                            f'keys, not {type(key)}')
        if len(key) != len(self._link_keys):
            raise ValueError('Link_Table[key] is only subscriptable with tuple '
                             f'keys of exactly length {len(self._link_keys)}')
        if not isinstance(value, dict):
            raise TypeError('Link_Table[key] = value is only assignable with '
                            f'row dictionaries, not {type(value)}')

        search_row: Row = dict(zip(self._link_keys, key))
        try:
            self.update(search_row, value)
        except KeyError:
            search_row.update(value)
            self.append(search_row)
