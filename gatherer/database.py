"""
Module that implements a connection to a MonetDB database.
"""

from builtins import object
import pymonetdb

class Database(object):
    """
    Database query utilities.
    """

    def __init__(self, **options):
        self._connection = pymonetdb.connect(**options)
        self._cursor = self._connection.cursor()

    def get_project_id(self, project_key):
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

        return str(row[0])

    def set_project_id(self, project_key):
        """
        Add the project key to the database with a new project ID.
        """

        self._cursor.execute('INSERT INTO gros.project(name) VALUES (%s)',
                             parameters=[project_key])

    def execute(self, query, parameters, update=False, one=False):
        """
        Perform a selection or update query.
        """

        self._cursor.execute(query, parameters=parameters)
        if update:
            self._connection.commit()
        elif one:
            return self._cursor.fetchone()
        else:
            return self._cursor.fetchall()

    def execute_many(self, query, parameter_sets):
        """
        Execute the same prepared query for all sequences of parameters
        and commit the changes.
        """

        self._cursor.executemany(query, parameter_sets)
        self._connection.commit()
