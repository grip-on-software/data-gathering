"""
Utilities for BigBoat API response data.

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
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Type, Union
import pymonetdb
from .database import Database
from .domain import Project
from .utils import convert_local_datetime, format_date, get_utc_datetime, parse_date

DetailsValue = Union[float, int]
Details = Mapping[str, Union[DetailsValue, Mapping[str, DetailsValue]]]

class Statuses:
    """
    Conversion of BigBoat status items to event records suitable for MonetDB.
    """

    MAX_BATCH_SIZE = 100

    def __init__(self, project: Project,
                 statuses: Optional[Sequence[Mapping[str, Any]]] = None,
                 source: Optional[str] = None, **options: Any) -> None:
        self._project = project
        self._project_id: Optional[int] = None

        self._database: Optional[Database] = None
        self._options = options

        if statuses is None:
            self._statuses: List[Mapping[str, Any]] = []
        else:
            self._statuses = list(statuses)

        self._source = source

    def __enter__(self) -> 'Statuses':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        self.close()

    def close(self) -> None:
        """
        Close the database connection if it is opened.
        """

        if self._database is not None:
            self._database.close()
            self._database = None

    @staticmethod
    def _find_details(details: Optional[Details], keys: Iterable[str],
                      subkey: Optional[str] = None) -> Optional[DetailsValue]:
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
    def from_api(cls, project: Project, statuses: Sequence[Mapping[str, Any]]) -> 'Statuses':
        """
        Convert an API result list of statuses into a list of dictionaries
        containing the relevant and status information, using the same keys
        for each status item.
        """

        details_values = ['usedIps', 'used', 'loadavg', 'time']
        details_max = ['totalIps', 'total']

        output = []
        for status in statuses:
            details: Optional[Details] = status.get('details')
            output.append({
                'name': status['name'],
                'checked_time': parse_date(status['lastCheck']['ISO']),
                'ok': status['isOk'],
                'value': cls._find_details(details, details_values, '15'),
                'max': cls._find_details(details, details_max, None)
            })

        return cls(project, output)

    @property
    def database(self) -> Optional[Database]:
        """
        Retrieve a database connection or `None` if the connection cannot
        be established due to a misconfiguration or unresponsive database.
        """

        if self._database is not None:
            return self._database

        try:
            self._database = Database(**self._options)
        except (EnvironmentError, pymonetdb.Error):
            pass

        return self._database

    @property
    def project_id(self) -> Optional[int]:
        """
        Retrieve the project identifier used for the project in the database,
        or `None` if the identifier cannot be retrieved.
        """

        if self._project_id is not None:
            return self._project_id

        if self.database is not None:
            self._project_id = self.database.get_project_id(self._project.key)

        return self._project_id

    def add_batch(self, statuses: Iterable[Mapping[str, Any]]) -> bool:
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

    def update(self) -> bool:
        """
        Add rows containing the BigBoat status information to the database.
        Returns whether the rows could be added to the database; database
        errors or unknown projects result in `False`.
        """

        if self.database is None or self.project_id is False:
            return False

        self._insert_source()

        # If the batch is empty, then we do not need to do anything else.
        if not self._statuses:
            return True

        query = '''INSERT INTO gros.bigboat_status
                   (project_id, name, checked_date, ok, value, max)
                   VALUES (%s, %s, %s, %s, %s, %s)'''
        parameters = []

        for status in self._statuses:
            checked_date = get_utc_datetime(status['checked_time'])
            checked_date = convert_local_datetime(checked_date)
            parameters.append([
                self.project_id, status['name'], format_date(checked_date),
                bool(int(status['ok'])), status.get('value'), status.get('max')
            ])

        self.database.execute_many(query, parameters)

        return True

    def _insert_source(self) -> None:
        if self._source is not None:
            return

        if self.database is None:
            raise TypeError('Database must be available')

        check_query = '''SELECT url FROM gros.source_environment
                         WHERE project_id = %s AND source_type = %s
                         AND url = %s AND environment = %s'''
        parameters = [self.project_id, 'bigboat', self._source, self._source]
        row = self.database.execute(check_query, parameters, one=True)
        if row is None:
            update_query = '''INSERT INTO gros.source_environment
                              (project_id, source_type, url, environment)
                              VALUES (%s, %s, %s, %s)'''
            self.database.execute(update_query, parameters, update=True)

    def export(self) -> Sequence[Mapping[str, Any]]:
        """
        Retrieve a list of dictionaries containing status records, suitable for
        export in JSON.
        """

        return self._statuses
