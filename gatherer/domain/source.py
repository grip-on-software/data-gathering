"""
Data source domain object
"""

import ConfigParser
import urlparse
from ..svn import Subversion_Repository
from ..git import Git_Repository

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

    @classmethod
    def _get_changed_host(cls, host):
        # Retrieve the changed host in the credentials configuration.
        if cls._credentials.has_option(host, 'host'):
            return cls._credentials.get(host, 'host')

        return host

    def _update_credentials(self):
        # Update the URL of a source when hosts change, and add any additional
        # credentials to the URL or source registry.
        parts = urlparse.urlsplit(self._plain_url)
        host = parts.netloc
        full_host = host
        if self._credentials.has_section(host):
            if self._follow_host_change:
                host = self._get_changed_host(host)

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

    @property
    def name(self):
        """
        Retrieve the name of the source.

        This is a potentially human-readable name of the source, but should be
        valid for use as an identifier, altough it may be non-unique and
        different between different source data.
        """

        return self._name

    @property
    def repository_class(self):
        """
        Retrieve the class that implements a version control repository pointing
        to this source.

        If this source has no repository, then this property returns `None`.
        """

        return None

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

    def __repr__(self):
        return repr(self.export())

    def __hash__(self):
        data = self.export()
        keys = sorted(data.keys())
        values = tuple(data[key] for key in keys)
        return hash(values)

    def __eq__(self, other):
        if not isinstance(other, Source):
            return False

        return self.export() == other.export()

    def __ne__(self, other):
        return not self.__eq__(other)

@Source_Types.register('subversion')
class Subversion(Source):
    """
    Subversion source information
    """

    @property
    def repository_class(self):
        return Subversion_Repository

@Source_Types.register('git')
class Git(Source):
    """
    Git source information
    """

    @property
    def repository_class(self):
        return Git_Repository

@Source_Types.register('gitlab')
@Source_Types.register('git',
                       lambda cls, follow_host_change=True, **source_data: \
                       cls.is_gitlab_url(source_data['url'],
                                         follow_host_change=follow_host_change))
class GitLab(Git):
    """
    GitLab source repository
    """

    def __init__(self, *args, **kwargs):
        self._host = None
        self._gitlab_token = None

        super(GitLab, self).__init__(*args, **kwargs)

    @classmethod
    def is_gitlab_url(cls, url, follow_host_change=True):
        """
        Check whether a given URL is part of a GitLab instance.
        """

        parts = urlparse.urlsplit(url)
        return cls.is_gitlab_host(parts.netloc,
                                  follow_host_change=follow_host_change)

    @classmethod
    def is_gitlab_host(cls, host, follow_host_change=True):
        """
        Check whether a given host (without scheme part) is a GitLab host.
        """

        cls._init_credentials()
        if follow_host_change:
            host = cls._get_changed_host(host)

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

        return self._host

    @property
    def gitlab_token(self):
        """
        Retrieve the token that is used for authenticating in the GitLab API.
        """

        return self._gitlab_token
