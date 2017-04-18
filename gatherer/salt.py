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
        self._database = Database(**options)

    def execute(self):
        """
        Retrieve or generate and update the project-specific salts.
        """

        project_id = self._database.get_project_id(self._project.key)
        if project_id is None:
            self._database.set_project_id(self._project.key)
            project_id = self._database.get_project_id(self._project.key)

        result = self._query(project_id)
        if not result:
            salt = bcrypt.gensalt()
            pepper = bcrypt.gensalt()
            self._update(project_id, salt, pepper)
        else:
            salt = result[0]
            pepper = result[1]

        return salt, pepper

    def _query(self, project_id):
        return self._database.execute('''SELECT salt, pepper
                                         FROM gros.project_salt
                                         WHERE project_id=%s''',
                                      parameters=[project_id], one=True)

    def _update(self, project_id, salt, pepper):
        self._database.execute('''INSERT INTO gros.project_salt(project_id,salt,pepper)
                                  VALUES (%s,%s,%s)''',
                               parameters=[project_id, salt, pepper],
                               update=True)
