"""
Module for synchronizing update tracker files.
"""

from builtins import object
import datetime
import logging
import os
import subprocess
import pymonetdb

class Update_Tracker(object):
    """
    Abstract source with update tracker files.
    """

    def __init__(self, project):
        self._project = project

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
        connection = pymonetdb.connect(**self._options)

        cursor = connection.cursor()
        cursor.execute('SELECT project_id FROM gros.project WHERE name=%s LIMIT 1',
                       parameters=[self._project.key])
        row = cursor.fetchone()
        if not row:
            logging.warning("Project '%s' is not in the database",
                            self._project.key)
            return

        project_id = row[0]

        cursor.execute('''SELECT filename, contents, update_date
                          FROM gros.update_tracker WHERE project_id=%s''',
                       parameters=[project_id])

        for row in cursor:
            filename, contents, update_date = row[0:3]
            # Update only specific files if given,
            if not files or filename in files:
                self.update_file(filename, contents, update_date)

        connection.close()

class SSH_Tracker(Update_Tracker):
    """
    External server with SSH public key authentication setup and a home
    directory containing (amongst others) update tracker files.
    """

    def __init__(self, project, username='', host=''):
        super(SSH_Tracker, self).__init__(project)
        self._username = username
        self._host = host

    def retrieve(self, files=None):
        if not files:
            # Cannot determine which files to retrieve.
            return

        auth = self._username + '@' + self._host
        path = '{}:~/{}'.format(auth, self._project.export_key)

        for filename in files:
            subprocess.call([
                'scp', '{}/{}'.format(path, filename),
                '{}/{}'.format(self._project.export_key, filename)
            ])