"""
Module for securely storing and retrieving project-specific encryption salts.
"""

from builtins import object
import bcrypt
from .database import Database

class Salt(object):
    """
    Encryption salt storage.
    """

    def __init__(self, project, **options):
        self._project = project
        self._project_id = None
        self._database = Database(**options)

    @property
    def project_id(self):
        """
        Retrieve the project ID for which we perform encryption.
        """

        if self._project_id is not None:
            return self._project_id

        self._project_id = self._database.get_project_id(self._project.key)
        if self._project_id is None:
            self._database.set_project_id(self._project.key)
            self._project_id = self._database.get_project_id(self._project.key)

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

        result = self._database.execute('''SELECT salt, pepper
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
        self._database.execute('''INSERT INTO gros.project_salt(project_id,salt,pepper)
                                  VALUES (%s,%s,%s)''',
                               parameters=[self.project_id, salt, pepper],
                               update=True)
