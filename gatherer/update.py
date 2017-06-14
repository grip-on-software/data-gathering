"""
Module for synchronizing update tracker files.
"""

from builtins import object
import datetime
import logging
import os
import subprocess
from .database import Database

class Update_Tracker(object):
    """
    Abstract source with update tracker files.
    """

    def __init__(self, project):
        self._project = project
        self._project.make_export_directory()

    def retrieve(self, files=None):
        """
        Retrieve the update tracker files with names `files` from the source.

        If `files` is not given or an empty sequence, then retrieve all files
        for this project from the remote source.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def update_file(self, filename, contents, update_date):
        """
        Check whether an update tracker file from a remote source is updated
        more recently than our local version, or the local version is missing,
        and update the local state if so.
        """

        logging.debug('Filename: %s, remote updated: %s', filename, update_date)

        path = os.path.join(self._project.export_key, filename)
        update = True
        if os.path.exists(path):
            file_date = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            logging.debug('FS updated: %s', file_date)
            if file_date >= update_date:
                logging.info('Update tracker %s: Already up to date.', filename)
                update = False

        if update:
            logging.info('Updating file %s from remote tracker file', filename)
            with open(path, 'w') as tracker_file:
                tracker_file.write(contents)

            times = (datetime.datetime.now(), update_date)
            os.utime(path, tuple(int(time.strftime('%s')) for time in times))

class Database_Tracker(Update_Tracker):
    """
    Database source with update tracker files.
    """

    def __init__(self, project, **options):
        super(Database_Tracker, self).__init__(project)
        self._options = options

    def retrieve(self, files=None):
        connection = Database(**self._options)

        project_id = connection.get_project_id(self._project.key)
        if project_id is None:
            logging.warning("Project '%s' is not in the database",
                            self._project.key)
            return

        result = connection.execute('''SELECT filename, contents, update_date
                                       FROM gros.update_tracker
                                       WHERE project_id=%s''',
                                    parameters=[project_id], one=False)

        for row in result:
            filename, contents, update_date = row[0:3]
            # Update only specific files if given,
            if not files or filename in files:
                self.update_file(filename, contents, update_date)

class SSH_Tracker(Update_Tracker):
    """
    External server with SSH public key authentication setup and a home
    directory containing (amongst others) update tracker files.
    """

    def __init__(self, project, user='', host='', key_path='~/.ssh/id_rsa'):
        super(SSH_Tracker, self).__init__(project)
        self._username = user
        self._host = host
        self._key_path = key_path

    def retrieve(self, files=None):
        if not files:
            # Cannot determine which files to retrieve.
            return

        auth = self._username + '@' + self._host
        path = '{}:~/{}'.format(auth, self._project.update_key)

        for filename in files:
            subprocess.call([
                'scp', '-i', self._key_path,
                '{}/{}'.format(path, filename),
                '{}/{}'.format(self._project.export_key, filename)
            ])
