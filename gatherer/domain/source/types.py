"""
Data source domain object
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import object
import os
try:
    import urllib.parse
except ImportError:
    raise
from ...config import Configuration

class Source_Type_Error(ValueError):
    """
    An error that the source type is not supported.
    """

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
            raise Source_Type_Error("Source type '{}' is not supported".format(source_type))

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
        self._credentials_path = None

        self._url = None
        if self._plain_url is None:
            self._host = None
        else:
            self._host = self._update_credentials()[1]

    @classmethod
    def _init_credentials(cls):
        if cls._credentials is None:
            cls._credentials = Configuration.get_credentials()

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
        if cls.has_option(host, 'host'):
            return cls._credentials.get(host, 'host')

        return host

    def _get_host_parts(self, parts):
        # Retrieve the changed host in the credentials configuration
        # Split the host into hostname and port if necessary.
        host = parts.netloc
        if self._follow_host_change and self.has_option(host, 'host'):
            host = self._credentials.get(host, 'host')
            split_host = host.split(':', 1)
            hostname = split_host[0]
            try:
                port = int(split_host[1])
            except (IndexError, ValueError):
                port = None
        else:
            hostname = parts.hostname
            try:
                port = parts.port
            except ValueError:
                port = None

        if self.has_option(host, 'port'):
            port = int(self._credentials.get(host, 'port'))

        return host, hostname, port

    @staticmethod
    def _create_url(*parts):
        # Cast to string to ensure that all parts have the same type.
        return urllib.parse.urlunsplit(tuple(str(part) for part in parts))

    def _update_credentials(self):
        # Update the URL of a source when hosts change, and add any additional
        # credentials to the URL or source registry.
        self._url = self._plain_url
        orig_parts = urllib.parse.urlsplit(self._plain_url)
        host = orig_parts.netloc

        if self._credentials.has_section(host):
            # Parse the host parts and potentially follow host changes.
            host, hostname, port = self._get_host_parts(orig_parts)

            username = self._credentials.get(host, 'username')
            if self.has_option(host, 'env'):
                # Use SSH URL, either short (user@host:path) or long version
                # (ssh://user@host:port/path) based on port requirement.
                # If 'strip' exists, then this value is stripped from the
                # beginning of the path.
                credentials_env = self._credentials.get(host, 'env')
                self._credentials_path = os.getenv(credentials_env)
                auth = username + '@' + hostname
                path = orig_parts.path
                if self.has_option(host, 'strip'):
                    strip = self._credentials.get(host, 'strip')
                    if path.startswith(strip):
                        path = path[len(strip):]
                    elif path.startswith('/' + strip):
                        path = path[len(strip)+1:]

                if self.has_option(host, 'port'):
                    if hostname.startswith('-'):
                        raise ValueError('Long SSH host may not begin with dash')

                    self._url = 'ssh://{0}:{1}{2}'.format(auth, port, path)
                else:
                    self._url = '{0}:{1}'.format(auth, path)
            elif self.has_option(host, 'password'):
                # Use HTTP(s) URL (http://username:password@host:port/path)
                password = urllib.parse.quote(self._credentials.get(host,
                                                                    'password'))

                auth = '{0}:{1}'.format(username, password)
                full_host = auth + '@' + hostname
                if port is not None:
                    full_host += ':{0}'.format(port)

                self._url = self._create_url(orig_parts.scheme, full_host,
                                             orig_parts.path, orig_parts.query,
                                             orig_parts.fragment)

        return orig_parts, host

    @property
    def plain_url(self):
        """
        Retrieve the URL as it is defined for the source.

        This does not contain changes to hosts or additions of credentials.
        """

        return self._plain_url

    @property
    def type(self):
        """
        Retrieve the literal type of the source, as it was initially defined.
        Note that some source classes register themselves for more than one type
        and there may be multiple classes registered for the same type.
        """

        return self._type

    @property
    def url(self):
        """
        Retrieve the final URL, after following host changes and including
        credentials where applicable
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
    def environment(self):
        """
        Retrieve an indicator of the environment that the source lives in.

        The environment is a shared signature with other Source objects that
        are situated on the same host or group. For example, Source objects that
        are retrieved using `get_sources` have this signature.

        The returned value is hashable.
        """

        return None

    @property
    def environment_url(self):
        """
        Retrieve a URL for the environment that the source lives in.

        The environment's URL is a human-readable site that describes the
        sources that are situated on the same host or group. For example, Source
        objects that are retrieved using `get_sources` have the same (base) URL.
        """

        return None

    @property
    def path_name(self):
        """
        Retrieve an identifier of the source that can be used as a path name.

        The path name is potentially non-unique.
        """

        return self.name

    @property
    def repository_class(self):
        """
        Retrieve the class that implements a version control repository pointing
        to this source.

        If this source has no repository, then this property returns `None`.
        """

        return None

    @property
    def credentials_path(self):
        """
        Retrieve a path to a file that contains credentials for this source.

        The file may be a SSH private key, depending on the source type.
        If there is no such file configured for this source, then this property
        returns `None`.
        """

        return self._credentials_path

    @credentials_path.setter
    def credentials_path(self, value):
        """
        Update the credentials path to another location.

        Note that this may set an SSH private key even though the connection is
        not using SSH.
        """

        self._credentials_path = value

    def get_option(self, option):
        """
        Retrieve an option from the credentials configuration of the host of
        this source.

        If the option does not exist or the value is one of 'false', 'no', '-'
        or the empty string, then `None` is returned.
        """

        if not self.has_option(self._host, option):
            return None

        return self._credentials.get(self._host, option)

    @classmethod
    def has_option(cls, host, option):
        """
        Check whether an option from the credentials configuration of the host
        of this source is available and not set to a falsy value.

        If the option does not exist or the value is one of 'false', 'no', '-'
        or the empty string, then `False` is returned. Otherwise, `True` is
        returned.
        """

        if not cls._credentials.has_option(host, option):
            return False

        value = cls._credentials.get(host, option)
        return Configuration.has_value(value)

    def check_credentials_environment(self):
        """
        Check whether this source's environment is within the restrictions of
        the credential settings for the source domain. This can be used to check
        if the source lives in a different environment than the one specified
        initially and that retrieving more sources from this environment would
        yield sources that we should not access for the current project.

        By default, we accept retrieving any environment sources, but source
        types can override this to use credential information to restrict this
        before attempting collection from that source.
        """

        return bool(self._host)

    def get_sources(self):
        """
        Retrieve information about additional data sources from the source.

        The return value is a list of `Source` objects. It may include sources
        that are already known or even the current source. If the source does
        not provide additional source information, then an empty list is
        returned.
        """

        return [self]

    def update_identity(self, project, public_key, dry_run=False):
        """
        Update the source to accept a public key as an identity for obtaining
        access to information or perform actions on the source.

        The `project` is a `Project` domain object providing details about the
        project for which this key is being added. The `public_key` is a string
        containing the contents of a public key that is part of a key pair used
        for credentials.

        The SSH key update removes any older keys for the identity, identified
        by the project, and registers the new public key. If `dry_run` is set
        to `True`, then no changes are actually made to the source, but logging
        may indicate what would happen.

        If the source does not support updating the SSH key or the update fails,
        then a `RuntimeError` is raised.
        """

        raise NotImplementedError('Cannot update SSH key for this source type')

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
