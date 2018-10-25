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
        self._open = True

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """
        Close the database connection.
        """

        if self._open:
            self._cursor.close()
            self._connection.close()
            self._open = False

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

    def execute_many(self, query, parameter_sets):
        """
        Execute the same prepared query for all sequences of parameters
        and commit the changes.
        """

        self._cursor.executemany(query, parameter_sets)
        self._connection.commit()
