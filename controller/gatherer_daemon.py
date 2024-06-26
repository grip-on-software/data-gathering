"""
Internal daemon for handling update tracking and project salt requests.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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

from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Mapping, Optional, Union, Sequence, Tuple
import pymonetdb
import Pyro4
from gatherer.bigboat import Statuses
from gatherer.config import Configuration
from gatherer.database import Database
from gatherer.domain import Project
from gatherer.files import File_Store
from gatherer.salt import Salt
from gatherer.update import Database_Tracker
from gatherer.utils import get_datetime, parse_date

@Pyro4.expose
class Gatherer:
    """
    Object that updates the agent directory and retrieves salts.
    """

    def __init__(self) -> None:
        self._config = Configuration.get_settings()
        self._options = {
            'user': self._config.get('database', 'username'),
            'password': self._config.get('database', 'password'),
            'host': self._config.get('database', 'host'),
            'database': self._config.get('database', 'name')
        }

    def get_database_status(self, project_key: str) -> Dict[str, Union[bool, str]]:
        """
        Retrieve status information from the database related to its
        availability and acceptance of new results.
        """

        try:
            with Database(**self._options) as database:
                if database.get_project_id(project_key) is not None:
                    return {'ok': True}

                return {
                    'ok': False,
                    'message': 'Project is not yet registered in the database'
                }
        except (OSError, pymonetdb.Error) as error:
            return {
                'ok': False,
                'message': str(error)
            }

    def _calculate_drift(self, project_key: str, today: datetime) -> timedelta:
        # Schedule drift: Next agent scrape may only occur after
        # $SCHEDULE_DAYS days, plus or minus a number of drift minutes.
        # Absolute value of drift minutes is up to $SCHEDULE_DRIFT minutes.
        # The drift minutes are hashed based on the project key, and to allow
        # projects to catch up, each schedule days period the drifts of each
        # project is swapped (negative instead of positive drift minutes).
        days = int(self._config.get('schedule', 'days'))
        drift = int(self._config.get('schedule', 'drift'))
        odd = (today.timetuple().tm_yday / days) % 2
        toggle = odd - 1 * (1 - odd)
        offset = toggle * (hash(project_key) % (drift * 2) - drift)

        return timedelta(days=days, minutes=offset)

    def get_tracker_schedule(self, project_key: str) -> timedelta:
        """
        Retrieve the scheduled time of the given project.
        This uses the update tracker file 'preflight_date.txt' to compare
        against the current date, to determine if the collected data is stale.

        Returns the time delta after which an agent may collect data for the
        project again. If the delta is less than or equal to zero, then data
        collection may resume immediately.

        This function may raise an exception which indicates that the update
        tracker is not available and data collection should be allowed as soon
        as no other issues arise.
        """

        project = Project(project_key)
        track = Database_Tracker(project, **self._options)
        filename = 'preflight_date.txt'
        try:
            content = track.retrieve_content(filename)
        except OSError as error:
            raise ValueError(f'Could not access update tracker from database: {error}') from error
        if content is None:
            raise ValueError(f'No update tracker {filename} found')

        try:
            tracker_date = get_datetime(parse_date(content))
        except ValueError as error:
            raise ValueError(f'Update tracker {filename} is unparseable: {error}') from error

        today = datetime.now()
        schedule = self._calculate_drift(project_key, today)
        interval = today - tracker_date
        return schedule - interval

    def update_tracker_schedule(self, project_key: str, contents: Optional[str] = None) -> None:
        """
        Update the scheduled time of the given project.
        This uses the update tracker file 'preflight_date.txt' to adjust when
        the collected data was most recently changed.

        The `contents`, if given, should be an ISO-formatted date time string
        for the claimed update moment. If it is not provided, then the tracker
        is set to the current time minus the schedule and drift of the project
        such that the schedule status is immediately set to allow collection
        of updates again.
        """

        if contents is None:
            today = datetime.now()
            schedule = self._calculate_drift(project_key, today)
            old_date = today - schedule
            contents = old_date.isoformat()

        project = Project(project_key)
        tracker = Database_Tracker(project, **self._options)
        filename = 'preflight_date.txt'
        tracker.put_content(filename, contents)

    def get_tracker_status(self, project_key: str) -> Dict[str, Union[bool, str]]:
        """
        Retrieve the status of the update tracker schedule of the given project.
        This uses the update tracker file 'preflight_date.txt' to compare
        against the current date, to determine if the collected data is stale.

        The status is a dictionary with at least a key 'ok' indicating the
        status, where `True` means an agent can collect data while `False`
        means no updates are necessary. Additionally, a key 'message' may
        provide a human-readable reason for the status.
        """

        try:
            delta = self.get_tracker_schedule(project_key)
        except ValueError as error:
            return {
                'ok': True,
                'message': str(error)
            }

        if delta <= timedelta(0):
            return {'ok': True}

        return {
            'ok': False,
            'message': f'Next scheduled gather moment is in {delta}'
        }

    def get_update_trackers(self, project_key: str, home_directory: str) -> None:
        """
        Retrieve update tracking files and store them in the agent's update
        directory.
        """

        # Put all update trackers in a separate directory.
        update_directory = Path(home_directory, 'update')

        project = Project(project_key,
                          export_directory=str(update_directory),
                          update_directory=str(update_directory))
        track = Database_Tracker(project, **self._options)
        track.retrieve()

        # Retrieve additional trackers.
        tracker_directory = Path('tracker', project_key)
        if tracker_directory.exists():
            for tracker_file in tracker_directory.iterdir():
                if not tracker_file.is_dir():
                    shutil.copy(str(tracker_file), str(project.export_key))

    def get_salts(self, project_key: str) -> Tuple[str, str]:
        """
        Retrieve project-specific encryption salts, or the global salt if
        `project_key` is the empty string.
        """

        if project_key == '':
            project = None
        else:
            project = Project(project_key)

        with Salt(project=project, **self._options) as salt:
            return salt.execute()

    def encrypt(self, project_key: str, value: str) -> str:
        """
        Retrieve an encrypted representation of the text value using the salt
        pair of the project `project_key` or the global salt if it is the empty
        string.
        """

        if project_key == '':
            project = None
        else:
            project = Project(project_key)

        with Salt(project=project, **self._options) as store:
            try:
                salt, pepper = store.get()
            except (RuntimeError, ValueError):
                return ''

            return store.encrypt(value.encode('utf-8'), salt.encode('utf-8'),
                                 pepper.encode('utf-8'))

    def get_usernames(self, project_key: str) -> List[Dict[str, str]]:
        """
        Retrieve username patterns that need to be replaced before encryption.
        """

        store_type = File_Store.get_type(self._config.get('dropins', 'type'))
        store = store_type(self._config.get('dropins', 'url'))
        store.login(self._config.get('dropins', 'username'),
                    self._config.get('dropins', 'password'))

        data_file = 'data_vcsdev_to_dev.json'
        usernames_file = store.get_file_contents(f'import/{data_file}')
        patterns = json.loads(usernames_file)
        usernames = []
        for pattern in patterns:
            if 'projects' in pattern and project_key in pattern['projects']:
                del pattern['projects']
                usernames.append(pattern)

        return usernames

    def add_bigboat_status(self, project_key: str,
                           statuses: Sequence[Mapping[str, Any]],
                           source: str) -> bool:
        """
        Add rows containing health status information from BigBoat for the
        given project to the database. Returns whether the rows could be added
        to the database; database errors or unknown projects result in `False`.
        """

        project = Project(project_key)
        with Statuses(project, statuses, source, **self._options) as status:
            return status.update()

def main() -> None:
    """
    Main setup and event loop.
    """

    daemon = Pyro4.Daemon()
    object_name_server = Pyro4.locateNS()
    uri = daemon.register(Gatherer)
    object_name_server.register("gros.gatherer", uri)

    daemon.requestLoop()

if __name__ == "__main__":
    main()
