"""
Module for synchronizing update tracker files.
"""

from datetime import datetime
import itertools
import logging
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Iterable, List, Optional, Union
from .database import Database
from .domain import Project

class Update_Tracker:
    """
    Abstract source with update tracker files.
    """

    def __init__(self, project: Project, **options: str) -> None:
        self._project = project
        self._options = options

    def retrieve(self, files: Optional[Iterable[str]] = None) -> None:
        """
        Retrieve the update tracker files with names `files` from the source,
        and place them in the export directory for the project.

        If `files` is not given or an empty sequence, then retrieve all files
        for this project from the remote source.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def retrieve_content(self, filename: str) -> Optional[str]:
        """
        Retrieve the contents of a single update tracker file with name
        `filename` from the source.

        The update tracker file is not stored locally. If the filename cannot
        be found remotely, then `None` is returned.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def put_content(self, filename: str, contents: str) -> None:
        """
        Update the remote update tracker file with the given contents.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def update_file(self, filename: str, contents: str, update_date: datetime) -> None:
        """
        Check whether an update tracker file from a remote source is updated
        more recently than our local version, or the local version is missing,
        and update the local state if so.
        """

        logging.debug('Filename: %s, remote updated: %s', filename, update_date)

        path = Path(self._project.export_key, filename)
        update = True
        if path.exists():
            file_date = datetime.fromtimestamp(path.stat().st_mtime)
            logging.debug('FS updated: %s', file_date)
            if file_date >= update_date:
                logging.info('Update tracker %s: Already up to date.', filename)
                update = False

        if update:
            logging.info('Updating file %s from remote tracker file', filename)
            with path.open('w') as tracker_file:
                tracker_file.write(contents)

            times = (int(datetime.now().strftime('%s')),
                     int(update_date.strftime('%s')))
            os.utime(path, times)

class Database_Tracker(Update_Tracker):
    """
    Database source with update tracker files.
    """

    def retrieve(self, files: Optional[Iterable[str]] = None) -> None:
        self._project.make_export_directory()
        with Database(**self._options) as database:
            project_id = database.get_project_id(self._project.key)
            if project_id is None:
                logging.warning("Project '%s' is not in the database",
                                self._project.key)
                return

            query = '''SELECT filename, contents, update_date
                       FROM gros.update_tracker
                       WHERE project_id=%s'''
            parameters: List[Union[int, str]] = [project_id]
            if files is not None:
                iters = itertools.tee(files, 2)
                query += ' AND filename IN (' + ','.join('%s' for _ in iters[0]) + ')'
                parameters.extend(iters[1])

            result = database.execute(query, parameters=parameters, one=False)

            if result is not None:
                for row in result:
                    filename, contents, update_date = row[0:3]
                    self.update_file(filename, contents, update_date)

    def retrieve_content(self, filename: str) -> Optional[str]:
        with Database(**self._options) as database:
            project_id = database.get_project_id(self._project.key)
            if project_id is None:
                logging.warning("Project '%s' is not in the database",
                                self._project.key)
                return None

            result = database.execute('''SELECT contents
                                         FROM gros.update_tracker
                                         WHERE project_id=%s
                                         AND filename=%s''',
                                      parameters=[project_id, filename],
                                      one=True)

            if result is None:
                return None

            return str(result[0])

    def put_content(self, filename: str, contents: str) -> None:
        with Database(**self._options) as database:
            project_id = database.get_project_id(self._project.key)
            if project_id is None:
                logging.warning("Project '%s' is not in the database",
                                self._project.key)

            database.execute('''UPDATE gros.update_tracker
                                SET contents=%s
                                WHERE project_id=%s
                                AND filename=%s''',
                             parameters=[contents, project_id, filename],
                             update=True)

class SSH_Tracker(Update_Tracker):
    """
    External server with SSH public key authentication setup and a home
    directory containing (amongst others) update tracker files.
    """

    def __init__(self, project: Project, user: str = '', host: str = '',
                 key_path: str = '~/.ssh/id_rsa') -> None:
        super(SSH_Tracker, self).__init__(project)
        self._username = user
        self._host = host
        self._key_path = key_path

    @property
    def remote_path(self) -> str:
        """
        Retrieve the remote path of the SSH server from which to retrieve
        update tracker files.
        """

        auth = self._username + '@' + self._host
        return f'{auth}:~/{self._project.update_key}'

    def retrieve(self, files: Optional[Iterable[str]] = None) -> None:
        self._project.make_export_directory()

        if not files:
            logging.warning('Cannot determine which files to retrieve')
            return

        args = ['scp', '-T', '-i', self._key_path] + [
            self.remote_path + '/\\{' + ','.join(files) + '\\}'
        ] + [str(self._project.export_key)]
        subprocess.call(args)

    def retrieve_content(self, filename: str) -> Optional[str]:
        try:
            return subprocess.check_output([
                'scp', '-i', self._key_path, f'{self.remote_path}/{filename}',
                '/dev/stdout'
            ])
        except subprocess.CalledProcessError:
            return None

    def put_content(self, filename: str, contents: str) -> None:
        with tempfile.NamedTemporaryFile(buffering=0) as temp_file:
            temp_file.write(contents)
            try:
                subprocess.run([
                    'scp', '-i', self._key_path,
                    temp_file.name, f'{self.remote_path}/{filename}'
                ])
            except subprocess.CalledProcessError:
                pass
