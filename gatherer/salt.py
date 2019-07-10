"""
Module for securely storing and retrieving project-specific encryption salts.
"""

import hashlib
import bcrypt
from .database import Database

class Salt:
    """
    Encryption salt storage.
    """

    def __init__(self, project=None, **options):
        self._project = project
        self._project_id = None
        self._database = None
        self._options = options

    @staticmethod
    def encrypt(value, salt, pepper):
        """
        Encode the string `value` using the provided `salt` and `pepper` hashes.
        """

        return hashlib.sha256(salt + value + pepper).hexdigest()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """
        Close the database connection.
        """

        if self._database is not None:
            self._database.close()
            self._database = None

    @property
    def database(self):
        """
        Retrieve the database connection.
        """

        if self._database is None:
            self._database = Database(**self._options)

        return self._database

    @property
    def project_id(self):
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
            self.database.set_project_id(self._project.key)
            self._project_id = self.database.get_project_id(self._project.key)

        return self._project_id

    def execute(self):
        """
        Retrieve or generate and update the project-specific salts.
        """

        result = self.get()
        if not result:
            return self.update()

        salt = result[0]
        pepper = result[1]

        return salt, pepper

    def get(self):
        """
        Retrieve the project-specific salts.
        """

        result = self.database.execute('''SELECT salt, pepper
                                          FROM gros.project_salt
                                          WHERE project_id=%s''',
                                       parameters=[self.project_id], one=True)

        return result

    def update(self):
        """
        Generate and update the project-specific salts.
        """

        salt = bcrypt.gensalt()
        pepper = bcrypt.gensalt()
        self._update(salt, pepper)

        return salt, pepper

    def _update(self, salt, pepper):
        self.database.execute('''INSERT INTO gros.project_salt(project_id,salt,pepper)
                                 VALUES (%s,%s,%s)''',
                              parameters=[self.project_id, salt, pepper],
                              update=True)
