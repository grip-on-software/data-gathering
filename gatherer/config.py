"""
Configuration provider.
"""

import os
import re
from configparser import RawConfigParser
from urlmatch.urlmatch import parse_match_pattern, BadMatchPattern

class Configuration:
    """
    Object that provides access to options and sections from configuration files
    that are stored alongside the repository or elsewhere.
    """

    _settings = None
    _credentials = None
    _url_blacklist = None

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

    @classmethod
    def has_value(cls, value):
        """
        Check whether the value of an option is not set to a falsy value.

        If the option is one of 'false', 'no', 'off', '-', '0', the empty
        string '' or `None`, then `False` is returned. Otherwise, `True` is
        returned.
        """

        return value not in ('false', 'no', 'off', '-', '0', '', None)

    @classmethod
    def get_agent_key(cls):
        """
        Retrieve the first configured project key.
        """

        return cls.get_settings().items('projects')[0][0].upper()

    @classmethod
    def get_url_blacklist(cls):
        """
        Retrieve a regular expression object that matches URLs that should not
        be requested by the gatherer because they are known to be inaccessible.
        """

        if cls._url_blacklist is None:
            # By default the blacklist matches nothing.
            cls._url_blacklist = re.compile('a^')
            if 'GATHERER_URL_BLACKLIST' in os.environ:
                patterns = os.environ['GATHERER_URL_BLACKLIST'].split(',')
                try:
                    blacklist = [parse_match_pattern(pattern,
                                                     path_required=False,
                                                     http_auth_allowed=True)
                                 for pattern in patterns]
                except BadMatchPattern:
                    blacklist = False
                if blacklist:
                    cls._url_blacklist = re.compile("|".join(blacklist))

        return cls._url_blacklist

    @classmethod
    def is_url_blacklisted(cls, url):
        """
        Check whether the provided URL should not be requested by the gatherer
        because it is known to be inaccessible.
        """

        return bool(cls.get_url_blacklist().match(url))
