"""
Module that implements a connection to a MonetDB database.

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

from types import TracebackType
from typing import Any, List, Optional, Sequence, Type, Union
import pymonetdb

class Database:
    """
    Database query utilities.
    """

    def __init__(self, **options: Any) -> None:
        self._open = False
        self._connection = pymonetdb.connect(**options)
        self._cursor = self._connection.cursor()
        self._open = True

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> 'Database':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        self.close()

    def close(self) -> None:
        """
        Close the database connection.
        """

        if self._open:
            self._cursor.close()
            self._connection.close()
            self._open = False

    def get_project_id(self, project_key: str) -> Optional[int]:
        """
        Retrieve the project ID from the database, or `None` if it is not
        in the database.
        """

        self._cursor.execute('''SELECT project_id FROM gros.project
                                WHERE name=%s LIMIT 1''',
                             parameters=[project_key])
        row = self._cursor.fetchone()
        if not row:
            return None

        return int(row[0])

    def set_project_id(self, project_key: str) -> int:
        """
        Add the project key to the database with a new project ID.
        """

        self._cursor.execute('INSERT INTO gros.project(name) VALUES (%s)',
                             parameters=[project_key])

        project_id = self.get_project_id(project_key)
        if project_id is None:
            raise RuntimeError('Database did not receive new project')

        return project_id

    def execute(self, query: str, parameters: Sequence[Any],
                update: bool = False, one: bool = False) -> \
                Optional[Union[List[Sequence], Sequence]]:
        """
        Perform a selection or update query.

        If `update` is `True`, then the query is executed and `None` is
        returned. Otherwise, if `one` is `True`, then one result row is
        returned. Otherwise (`update` and `one` are both `False`, which is the
        default), then a list of result rows is returned.
        """

        self._cursor.execute(query, parameters=parameters)
        if update:
            self._connection.commit()
            return None

        if one:
            return self._cursor.fetchone()

        return self._cursor.fetchall()

    def execute_many(self, query: str, parameter_sets: Sequence[Sequence[Any]]) -> None:
        """
        Execute the same prepared query for all sequences of parameters
        and commit the changes.
        """

        self._cursor.executemany(query, parameter_sets)
        self._connection.commit()
