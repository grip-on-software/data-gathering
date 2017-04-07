"""
Module that supports retrieving auxiliary files from a data store.
"""

from builtins import object
import tempfile
from zipfile import ZipFile
import owncloud

class PathExistenceError(RuntimeError):
    """
    An exception that indicates that a certain file or directory was not found
    in the file store.
    """

    pass

class File_Store(object):
    """
    File store abstract class.
    """

    def login(self, username, password):
        """
        Log in to the store, if the store makes use of user- and password-based
        authentication.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_file(self, remote_file, local_file):
        """
        Retrieve the file from the remote path `remote_file` and store it in the
        local path `local_file`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_directory(self, remote_path, local_path):
        """
        Retrieve all files in the direcotry with the remote path `remote_path`
        and store them in the local path `local_path`.
        """
        raise NotImplementedError('Must be implemented by subclasses')

    def put_file(self, local_file, remote_file):
        """
        Upload the contents of the file from the local path `local_file` to
        the store at the remote path `remote_file`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def put_directory(self, local_path, remote_path):
        """
        Upload an entire directory and all its subdirectories and files in them
        from the local path `local_path` to the store path `remote_path`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class OwnCloud_Store(File_Store):
    """
    File store using an ownCloud backend.
    """

    def __init__(self, url):
        self._client = owncloud.Client(url)

    def login(self, username, password):
        self._client.login(username, password)

    def get_file(self, remote_file, local_file):
        try:
            self._client.get_file(remote_file, local_file)
        except owncloud.HTTPResponseError as error:
            if error.status_code == 404:
                raise PathExistenceError(remote_file)
            else:
                raise error

    def get_directory(self, remote_path, local_path):
        # Retrieve the directory as zip file
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            zip_file_name = tmpfile.name

        try:
            self._client.get_directory_as_zip(remote_path, zip_file_name)
        except owncloud.HTTPResponseError as error:
            if error.status_code == 404:
                raise PathExistenceError(remote_path)
            else:
                raise error

        with ZipFile(zip_file_name, 'r') as zip_file:
            zip_file.extractall(local_path)

    def put_file(self, local_file, remote_file):
        self._client.put_file(remote_file, local_file)

    def put_directory(self, local_path, remote_path):
        self._client.put_directory(remote_path, local_path)
