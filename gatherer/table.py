"""
Table structures.

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

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from copy import copy, deepcopy
from .salt import Salt

PathLike = Union[str, os.PathLike]
Value = str
Row = Dict[str, Value]

class Table:
    """
    Data storage for eventual JSON output for the database importer.
    """

    def __init__(self, name: str, filename: Optional[str] = None,
                 merge_update: bool = False,
                 encrypt_fields: Optional[Sequence[str]] = None) -> None:
        self._name = name
        self._data: List[Row] = []
        self._merge_update = merge_update
        self._encrypt_fields = encrypt_fields

        secrets_path = Path('secrets.json')
        self._secrets: Optional[Dict[str, Any]] = None
        if self._encrypt_fields is not None and secrets_path.exists():
            with secrets_path.open('r', encoding='utf-8') as secrets_file:
                self._secrets = json.load(secrets_file)

        if filename is None:
            self._filename = f'data_{self._name}.json'
        else:
            self._filename = filename

    @property
    def name(self) -> str:
        """
        Retrieve the name of the table.
        """

        return self._name

    def _convert_username(self, username: str) -> str:
        if self._secrets is None:
            return username

        for search_set in self._secrets['usernames']:
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
            if field not in row:
                # Sparse tables may not contain every row
                continue

            if 'usernames' in self._secrets and field.endswith('username'):
                row[field] = self._convert_username(row[field])

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
        Check whether the `row` (or an identifier contained within) already
        exists within the table.

        The default Table implementation uses a slow linear comparison, but
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

    def append(self, row: Row) -> bool:
        """
        Insert a row into the table.
        Subclasses may check whether the row (or some identifier in it) already
        exists in the table, and ignore it if this is the case.
        The return value indicates whether the row is newly added to the table.
        """

        self._data.append(self._encrypt(row))
        return True

    def extend(self, rows: Sequence[Row]) -> None:
        """
        Insert multiple rows at once into the table.
        """

        self._data.extend([self._encrypt(row) for row in rows])

    def update(self, search_row: Row, update_row: Row) -> None:
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

class Key_Table(Table):
    """
    Data storage for a table that has a primary, unique key.

    The table checks whether any row with some key was already added before
    accepting a new row with that key
    """

    def __init__(self, name: str, key: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self._key = key
        self._keys: Dict[str, Row] = {}

    def has(self, row: Row) -> bool:
        return row[self._key] in self._keys

    def _fetch_row(self, row: Row) -> Row:
        key = row[self._key]
        return self._keys[key]

    def append(self, row: Row) -> bool:
        if self.has(row):
            return False

        key = row[self._key]
        self._keys[key] = row
        return super().append(row)

    def extend(self, rows: Sequence[Row]) -> None:
        for row in rows:
            self.append(row)

    def update(self, search_row: Row, update_row: Row) -> None:
        if self._key in update_row:
            raise KeyError(f'Key {self._key} may not be provided in update row')

        super().update(search_row, update_row)

class Link_Table(Table):
    """
    Data storage for a table that has a combination of columns that make up
    a primary key.
    """

    def __init__(self, name: str, link_keys: Sequence[str], **kwargs) -> None:
        super().__init__(name, **kwargs)
        self._link_keys = link_keys
        self._links: Dict[Tuple[str, ...], Row] = {}

    def _build_key(self, row: Row) -> Tuple[str, ...]:
        # Link values used in the key must be hashable
        return tuple(row[key] for key in self._link_keys)

    def has(self, row: Row) -> bool:
        return self._build_key(row) in self._links

    def _fetch_row(self, row: Row) -> Row:
        key = self._build_key(row)
        return self._links[key]

    def append(self, row: Row) -> bool:
        link_values = self._build_key(row)
        if link_values in self._links:
            return False

        self._links[link_values] = row
        return super().append(row)

    def extend(self, rows: Sequence[Row]) -> None:
        for row in rows:
            self.append(row)

    def update(self, search_row: Row, update_row: Row) -> None:
        disallowed_keys = set(self._link_keys).intersection(update_row.keys())
        if disallowed_keys:
            key_text = 'Key' if len(disallowed_keys) == 1 else 'Keys'
            disallowed = ', '.join(disallowed_keys)
            raise KeyError(f'{key_text} {disallowed} may not be provided in update row')

        super().update(search_row, update_row)
