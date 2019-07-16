"""
Module for securely storing and retrieving project-specific encryption salts.
"""

import hashlib
from typing import Any, Optional, Tuple, TYPE_CHECKING
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

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
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

        result = self.get()
        if not result:
            return self.update()

        salt = result[0]
        pepper = result[1]

        return salt, pepper

    def get(self) -> Tuple[str, str]:
        """
        Retrieve the project-specific salts.
        """

        result = self.database.execute('''SELECT salt, pepper
                                          FROM gros.project_salt
                                          WHERE project_id=%d''',
                                       parameters=[self.project_id],
                                       one=True)

        if result is None:
            raise TypeError('Unexpected result')

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
                                 VALUES (%d,%s,%s)''',
                              parameters=[self.project_id, salt, pepper],
                              update=True)
