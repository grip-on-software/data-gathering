"""
Module that supports retrieving auxiliary files from a data store.

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

from pathlib import Path, PurePath
import shutil
import tempfile
from typing import Callable, Dict, Type
from zipfile import ZipFile
import owncloud

S_type = Type['File_Store']

class PathExistenceError(RuntimeError):
    """
    An exception that indicates that a certain file or directory was not found
    in the file store.
    """

class File_Store:
    """
    File store abstract class.
    """

    _store_types: Dict[str, S_type] = {}

    @classmethod
    def register(cls, store_type: str) -> Callable[[S_type], S_type]:
        """
        Decorator method for a class that registers a certain `store_type`.
        """

        def decorator(subject: S_type) -> S_type:
            """
            Decorator that registers the class `subject` to the store type.
            """

            cls._store_types[store_type] = subject

            return subject

        return decorator

    @classmethod
    def get_type(cls, store_type: str) -> S_type:
        """
        Retrieve the class registered for the given `store_type` string.
        """

        if store_type not in cls._store_types:
            raise RuntimeError(f'Store type {store_type} is not supported')

        return cls._store_types[store_type]

    def __init__(self, url: str) -> None:
        pass

    def login(self, username: str, password: str) -> None:
        """
        Log in to the store, if the store makes use of user- and password-based
        authentication.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_file(self, remote_file: str, local_file: str) -> None:
        """
        Retrieve the file from the remote path `remote_file` and store it in the
        local path `local_file`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_file_contents(self, remote_file: str) -> str:
        """
        Retrieve the file contents from the remote path `remote_file` without
        storing it in a (presistent) local path.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def get_directory(self, remote_path: str, local_path: str) -> None:
        """
        Retrieve all files in the direcotry with the remote path `remote_path`
        and store them in the local path `local_path` which does not yet exist.
        """
        raise NotImplementedError('Must be implemented by subclasses')

    def put_file(self, local_file: str, remote_file: str) -> None:
        """
        Upload the contents of the file from the local path `local_file` to
        the store at the remote path `remote_file`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def put_directory(self, local_path: str, remote_path: str) -> None:
        """
        Upload an entire directory and all its subdirectories and files in them
        from the local path `local_path` to the store path `remote_path`.
        """

        raise NotImplementedError('Must be implemented by subclasses')

@File_Store.register('owncloud')
class OwnCloud_Store(File_Store):
    """
    File store using an ownCloud backend.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url)
        self._client = owncloud.Client(url)

    def login(self, username: str, password: str) -> None:
        self._client.login(username, password)

    def get_file(self, remote_file: str, local_file: str) -> None:
        try:
            self._client.get_file(remote_file, local_file)
        except owncloud.HTTPResponseError as error:
            if error.status_code == 404:
                raise PathExistenceError(remote_file) from error
            raise RuntimeError(error.get_resource_body()) from error

    def get_file_contents(self, remote_file: str) -> str:
        return self._client.get_file_contents(remote_file)

    def get_directory(self, remote_path: str, local_path: str) -> None:
        # Retrieve the directory as zip file
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            zip_file_name = str(tmpfile.name)

        try:
            self._client.get_directory_as_zip(remote_path, zip_file_name)
        except owncloud.HTTPResponseError as error:
            if error.status_code == 404:
                raise PathExistenceError(remote_path) from error
            raise error

        extract_path = tempfile.mkdtemp()
        with ZipFile(zip_file_name, 'r') as zip_file:
            zip_file.extractall(extract_path)

        zip_inner_path = PurePath(remote_path.rstrip('/')).name
        full_path = Path(extract_path, zip_inner_path)
        shutil.move(str(full_path), str(local_path))

    def put_file(self, local_file: str, remote_file: str) -> None:
        self._client.put_file(remote_file, local_file)

    def put_directory(self, local_path: str, remote_path: str) -> None:
        self._client.put_directory(remote_path, local_path)
