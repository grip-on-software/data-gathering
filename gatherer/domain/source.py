"""
Data source domain object
"""

import ConfigParser
import urlparse

class Source_Types(object):
    """
    Holder for source type registration
    """

    _validated_types = {}
    _types = {}

    @classmethod
    def register(cls, source_type, validator=None):
        """
        Decorator method for a class that registers a certain `source_type`.
        """

        def decorator(subject):
            """
            Decorator that registers the class `subject` to the source type.
            """

            if validator is not None:
                if source_type not in cls._validated_types:
                    cls._validated_types[source_type] = []

                cls._validated_types[source_type].append((subject, validator))
            else:
                cls._types[source_type] = subject

            return subject

        return decorator

    @classmethod
    def get_source(cls, source_type, **source_data):
        """
        Retrieve an object that represents a fully-instantiated source with
        a certain type.
        """

        source_class = None
        if source_type in cls._validated_types:
            for candidate_class, validator in cls._validated_types[source_type]:
                if validator(candidate_class, **source_data):
                    source_class = candidate_class
                    break

        if source_class is None and source_type in cls._types:
            source_class = cls._types[source_type]

        if source_class is None:
            raise ValueError("Source type '{}' is not supported".format(source_type))

        return source_class(source_type, **source_data)

class Source(object):
    """
    Interface for source information about various types of data sources.
    """

    _credentials = None

    def __init__(self, source_type, name=None, url=None, follow_host_change=True):
        self._init_credentials()
        self._name = name
        self._plain_url = url
        self._type = source_type
        self._follow_host_change = follow_host_change

        self._url = None
        self._update_credentials()

    @classmethod
    def _init_credentials(cls):
        if cls._credentials is None:
            cls._credentials = ConfigParser.RawConfigParser()
            cls._credentials.read("credentials.cfg")

    @classmethod
    def from_type(cls, source_type, **kwargs):
        """
        Create a fully-instantiated source object from its source type.

        Returns an object of the appropriate type.
        """

        return Source_Types.get_source(source_type, **kwargs)

    def _update_credentials(self):
        # Update the URL of a source when hosts change, and add any additional
        # credentials to the URL or source registry.
        parts = urlparse.urlsplit(self._plain_url)
        host = parts.netloc
        full_host = host
        if self._credentials.has_section(host):
            if self._follow_host_change and self._credentials.has_option(host, 'host'):
                host = self._credentials.get(host, 'host')

            username = self._credentials.get(host, 'username')
            password = self._credentials.get(host, 'password')

            auth = '{0}:{1}'.format(username, password)
            full_host = auth + '@' + host

        new_parts = (parts.scheme, full_host, parts.path, parts.query,
                     parts.fragment)
        self._url = urlparse.urlunsplit(new_parts)
        return parts, host

    @property
    def url(self):
        """
        Retrieve the URL with credentials.
        """

        return self._url

    def export(self):
        """
        Retrieve a dictionary that can be exported to JSON with data about
        the current source.
        """

        return {
            'name': self._name,
            'url': self._plain_url,
            'type': self._type
        }

@Source_Types.register('subversion')
class Subversion(Source):
    """
    Subversion source information
    """

    pass

@Source_Types.register('git')
class Git(Source):
    """
    Git source information
    """

    pass

@Source_Types.register('gitlab')
@Source_Types.register('git', lambda cls, **source_data: cls.is_gitlab_url(source_data['url']))
class GitLab(Git):
    """
    GitLab source repository
    """

    def __init__(self, *args, **kwargs):
        self._host = None
        self._gitlab_token = None

        super(GitLab, self).__init__(*args, **kwargs)

    @classmethod
    def is_gitlab_url(cls, url):
        """
        Check whether a given URL is part of a GitLab instance.
        """

        parts = urlparse.urlsplit(url)
        return cls.is_gitlab_host(parts.netloc)

    @classmethod
    def is_gitlab_host(cls, host):
        """
        Check whether a given host (without scheme part) is a GitLab host.
        """

        cls._init_credentials()
        return cls._credentials.has_option(host, 'gitlab_token')

    def _update_credentials(self):
        parts, host = super(GitLab, self)._update_credentials()

        if self._credentials.has_option(host, 'gitlab_token'):
            self._gitlab_token = self._credentials.get(host, 'gitlab_token')

        host_parts = (parts.scheme, host, '', '', '')
        self._host = urlparse.urlunsplit(host_parts)

        return parts, host

    @property
    def host(self):
        """
        Retrieve the host name with scheme part of the GitLab instance.
        """

        print self._plain_url
        print self._host
        return self._host

    @property
    def gitlab_token(self):
        """
        Retrieve the token that is used for authenticating in the GitLab API.
        """

        return self._gitlab_token
