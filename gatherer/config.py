"""
Configuration provider.
"""

import os
from configparser import RawConfigParser

class Configuration(object):
    """
    Object that provides access to options and sections from configuration files
    that are stored alongside the repository or elsewhere.
    """

    _settings = None
    _credentials = None

    @classmethod
    def get_filename(cls, file_name):
        """
        Retrieve the file name to be used to retrieve the configuration.
        """

        environment_var = 'GATHERER_{}_FILE'.format(file_name.upper())
        if environment_var in os.environ:
            return os.environ[environment_var]

        return '{}.cfg'.format(file_name)

    @classmethod
    def get_config(cls, file_name):
        """
        Create a configuration object that is loaded with options from a file.
        """

        config = RawConfigParser()
        config.read(cls.get_filename(file_name))

        return config

    @classmethod
    def get_settings(cls):
        """
        Retrieve the settings configuration object.
        """

        if cls._settings is None:
            cls._settings = cls.get_config('settings')

        return cls._settings

    @classmethod
    def get_credentials(cls):
        """
        Retrieve the credentials configuration object.
        """

        if cls._credentials is None:
            cls._credentials = cls.get_config('credentials')

        return cls._credentials
