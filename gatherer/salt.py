"""
Module for securely storing and retrieving project-specific encryption salts.

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

import hashlib
from types import TracebackType
from typing import Any, Optional, Tuple, Type, TYPE_CHECKING
import bcrypt
from .database import Database
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .domain import Project
else:
    Project = object

class Salt:
    """
    Encryption salt storage.
    """

    def __init__(self, project: Optional[Project] = None, **options: Any) -> None:
        self._project = project
        self._project_id: Optional[int] = None
        self._database: Optional[Database] = None
        self._options = options

    @staticmethod
    def encrypt(value: bytes, salt: bytes, pepper: bytes) -> str:
        """
        Encode the string `value` using the provided `salt` and `pepper` hashes.
        """

        return hashlib.sha256(salt + value + pepper).hexdigest()

    def __enter__(self) -> 'Salt':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        self.close()

    def close(self) -> None:
        """
        Close the database connection.
        """

        if self._database is not None:
            self._database.close()
            self._database = None

    @property
    def database(self) -> Database:
        """
        Retrieve the database connection.
        """

        if self._database is None:
            self._database = Database(**self._options)

        return self._database

    @property
    def project_id(self) -> int:
        """
        Retrieve the project ID for which we perform encryption.
        """

        if self._project_id is not None:
            return self._project_id

        if self._project is None:
            self._project_id = 0
            return self._project_id

        self._project_id = self.database.get_project_id(self._project.key)
        if self._project_id is None:
            self._project_id = self.database.set_project_id(self._project.key)

        return self._project_id

    def execute(self) -> Tuple[str, str]:
        """
        Retrieve or generate and update the project-specific salts.
        """

        try:
            result = self.get()
        except ValueError:
            return self.update()

        salt = result[0]
        pepper = result[1]

        return salt, pepper

    def get(self) -> Tuple[str, str]:
        """
        Retrieve the project-specific salts.

        If the salts are not available for the project then a `ValueError` is
        raised.
        """

        result = self.database.execute('''SELECT salt, pepper
                                          FROM gros.project_salt
                                          WHERE project_id=%s''',
                                       parameters=[self.project_id],
                                       one=True)

        if result is None:
            raise ValueError('No salts stored for project')

        return str(result[0]), str(result[1])

    def update(self) -> Tuple[str, str]:
        """
        Generate and update the project-specific salts.
        """

        salt = bcrypt.gensalt().decode('utf-8')
        pepper = bcrypt.gensalt().decode('utf-8')
        self._update(salt, pepper)

        return salt, pepper

    def _update(self, salt: str, pepper: str) -> None:
        self.database.execute('''INSERT INTO gros.project_salt(project_id,salt,pepper)
                                 VALUES (%s,%s,%s)''',
                              parameters=[self.project_id, salt, pepper],
                              update=True)
