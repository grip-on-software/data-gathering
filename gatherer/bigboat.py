"""
Utilities for BigBoat API response data.
"""

import pymonetdb
from .database import Database
from .utils import convert_utc_datetime, get_datetime, parse_date

class Statuses(object):
    """
    Conversion of BigBoat status items to event records suitable for MonetDB.
    """

    MAX_BATCH_SIZE = 100

    def __init__(self, project, statuses=None, **options):
        self._project = project
        self._project_id = None

        self._database = None
        self._options = options

        if statuses is None:
            self._statuses = []
        else:
            self._statuses = statuses

    @staticmethod
    def _find_details(details, keys, subkey=None):
        """
        Retrieve a relevant numeric value from a details dictionary.
        """

        if details is None:
            return None

        for key in keys:
            if key in details:
                value = details[key]
                if isinstance(value, (float, int)):
                    return value
                if subkey is not None and subkey in value:
                    return value[subkey]

                raise ValueError('Value is not numeric and does not hold the subkey')

        return None

    @classmethod
    def from_api(cls, project, statuses):
        """
        Convert an API result list of statuses into a list of dictionaries
        containing the relevant and status information, using the same keys
        for each status item.
        """

        details_values = ['usedIps', 'used', 'loadavg', 'time']
        details_max = ['totalIps', 'total']

        output = []
        for status in statuses:
            details = status.get('details')
            output.append({
                'name': status['name'],
                'checked_time': parse_date(status['lastCheck']['ISO']),
                'ok': status['isOk'],
                'value': cls._find_details(details, details_values, '15'),
                'max': cls._find_details(details, details_max, None)
            })

        return cls(project, output)

    @property
    def database(self):
        """
        Retrieve a database connection or `False` if the connection cannot
        be established due to a misconfiguration or unresponsive database.
        """

        if self._database is not None:
            return self._database

        try:
            self._database = Database(**self._options)
        except (EnvironmentError, pymonetdb.Error):
            self._database = False

        return self._database

    @property
    def project_id(self):
        """
        Retrieve the project identifier used for the project in the database,
        or `False` if the identifier cannot be retrieved.
        """

        if self._project_id is not None:
            return self._project_id

        if self.database is False:
            self._project_id = False
        else:
            self._project_id = self.database.get_project_id(self._project.key)
            if self._project_id is None:
                self._project_id = False

        return self._project_id

    def add_batch(self, statuses):
        """
        Add new statuses to the batch, and optionally update the database with the
        current batch if it becomes too large. Returns whether the loaded data is
        still intact, i.e., the status records are either in the batch or in the
        database; misconfigurations result in `False`.
        """

        if len(self._statuses) > self.MAX_BATCH_SIZE:
            result = self.update()
            self._statuses = []
        else:
            result = True

        self._statuses.extend(statuses)
        return result

    def update(self):
        """
        Add rows containing the BigBoat status information to the database.
        Returns whether the rows could be added to the database; database
        errors or unknown projects result in `False`.
        """

        if self.database is False or self.project_id is False:
            return False

        # If the batch is empty, then we do not need to do anything else.
        if not self._statuses:
            return True

        query = '''INSERT INTO gros.bigboat_status
                   (project_id, name, checked_date, ok, value, max)
                   VALUES (%s, %s, %s, %s, %s, %s)'''
        parameters = []

        for status in self._statuses:
            checked_date = get_datetime(status['checked_time'])
            checked_date = convert_utc_datetime(checked_date)
            parameters.append([
                self.project_id, status['name'], checked_date,
                bool(int(status['ok'])), status.get('value'), status.get('max')
            ])

        self.database.execute_many(query, parameters)

        return True

    def export(self):
        """
        Retrieve a list of dictionaries containing status records, suitable for
        export in JSON.
        """

        return self._statuses
