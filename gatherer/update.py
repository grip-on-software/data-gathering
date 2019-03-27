"""
Module for synchronizing update tracker files.
"""

from builtins import object
import datetime
import logging
import os
import subprocess
import tempfile
from .database import Database

class Update_Tracker(object):
    """
    Abstract source with update tracker files.
    """

    def __init__(self, project):
        self._project = project

    def retrieve(self, files=None):
        """
        Retrieve the update tracker files with names `files` from the source,
        and place them in the export directory for the project.

        If `files` is not given or an empty sequence, then retrieve all files
        for this project from the remote source.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def retrieve_content(self, filename):
        """
        Retrieve the contents of a single update tracker file with name
        `filename` from the source.

        The update tracker file is not stored locally. If the filename cannot
        be found remotely, then `None` is returned.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def put_content(self, filename, contents):
        """
        Update the remote update tracker file with the given contents.
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
        self._project.make_export_directory()
        with Database(**self._options) as database:
            project_id = database.get_project_id(self._project.key)
            if project_id is None:
                logging.warning("Project '%s' is not in the database",
                                self._project.key)
                return

            result = database.execute('''SELECT filename, contents, update_date
                                         FROM gros.update_tracker
                                         WHERE project_id=%s''',
                                      parameters=[project_id], one=False)

            for row in result:
                filename, contents, update_date = row[0:3]
                # Update only specific files if given,
                if not files or filename in files:
                    self.update_file(filename, contents, update_date)

    def retrieve_content(self, filename):
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

            return result[0]

    def put_content(self, filename, contents):
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

    def __init__(self, project, user='', host='', key_path='~/.ssh/id_rsa'):
        super(SSH_Tracker, self).__init__(project)
        self._username = user
        self._host = host
        self._key_path = key_path

    @property
    def remote_path(self):
        """
        Retrieve the remote path of the SSH server from which to retrieve
        update tracker files.
        """

        auth = self._username + '@' + self._host
        return '{}:~/{}'.format(auth, self._project.update_key)

    def retrieve(self, files=None):
        self._project.make_export_directory()

        if not files:
            logging.warning('Cannot determine which files to retrieve')
            return

        args = ['scp', '-T', '-i', self._key_path] + [
            self.remote_path + '/\\{' + ','.join(files) + '\\}'
        ] + [self._project.export_key]
        subprocess.call(args)

    def retrieve_content(self, filename):
        try:
            return subprocess.check_output([
                'scp', '-i', self._key_path,
                '{}/{}'.format(self.remote_path, filename),
                '/dev/stdout'
            ])
        except subprocess.CalledProcessError:
            return None

    def put_content(self, filename, contents):
        with tempfile.NamedTemporaryFile(buffering=0) as temp_file:
            temp_file.write(contents)
            try:
                subprocess.run([
                    'scp', '-i', self._key_path,
                    temp_file.name, '{}/{}'.format(self.remote_path, filename)
                ])
            except subprocess.CalledProcessError:
                pass
