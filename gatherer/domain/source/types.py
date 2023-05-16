"""
Data source domain object.

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

import os
from pathlib import Path
from typing import Any, AnyStr, Callable, ClassVar, Dict, Hashable, List, \
    Optional, Tuple, Type, Union, TYPE_CHECKING
from urllib.parse import quote, urlsplit, urlunsplit, SplitResult
from ...config import Configuration
from ...version_control.repo import Version_Control_Repository
if TYPE_CHECKING:
    # pylint: disable=cyclic-import, unsubscriptable-object
    from ..project import Project
    PathLike = Union[str, os.PathLike[str]]
else:
    Project = object
    PathLike = os.PathLike


class Source_Type_Error(ValueError):
    """
    An error that the source type is not supported.
    """

Validator = Callable[..., bool]
S_type = Type['Source']

class Source_Types:
    """
    Holder for source type registration
    """

    _validated_types: ClassVar[Dict[str, List[Tuple[S_type, Validator]]]] = {}
    _types: ClassVar[Dict[str, S_type]] = {}

    @classmethod
    def register(cls, source_type: str,
                 validator: Optional[Validator] = None) -> Callable[[S_type], S_type]:
        """
        Decorator method for a class that registers a certain `source_type`.
        """

        def decorator(subject: S_type) -> S_type:
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
    def get_source(cls, source_type: str, **source_data: Any) -> 'Source':
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
            raise Source_Type_Error(f"Source type '{source_type}' is not supported")

        return source_class(source_type, **source_data)

# Seven instance attributes in __init__, but pylint incorrectly counts
# a property setter in use to be an instance attribute as well
# https://github.com/PyCQA/pylint/issues/4100
class Source: # pylint: disable=too-many-instance-attributes
    """
    Interface for source information about various types of data sources.
    """

    HTTP_PROTOCOLS = ('http', 'https')
    SSH_PROTOCOL = 'ssh'

    _credentials = Configuration.get_credentials()

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True) -> None:
        self._name = name
        self._plain_url = url
        self._type = source_type
        self._follow_host_change = follow_host_change
        self._credentials_path: Optional[PathLike] = None

        self._url = url
        self._host = self._update_credentials()[1]

    @classmethod
    def from_type(cls, source_type: str, **kwargs: Any) -> 'Source':
        """
        Create a fully-instantiated source object from its source type.

        Returns an object of the appropriate type.
        """

        return Source_Types.get_source(source_type, **kwargs)

    @classmethod
    def _get_changed_host(cls, host: str) -> str:
        # Retrieve the changed host in the credentials configuration.
        if cls.has_option(host, 'host'):
            return cls._credentials.get(host, 'host')

        return host

    def _get_host_parts(self, host: str, parts: SplitResult) -> Tuple[str, Optional[int]]:
        # Retrieve the changed host in the credentials configuration
        # Split the host into hostname and port if necessary.
        port: Optional[int] = None
        if self._follow_host_change and self.has_option(host, 'host'):
            host = self._credentials.get(host, 'host')
            split_host = host.split(':', 1)
            hostname = split_host[0]
            try:
                port = int(split_host[1])
            except (IndexError, ValueError):
                pass
        else:
            if parts.hostname is None:
                return '', None

            hostname = parts.hostname
            try:
                port = parts.port
            except ValueError:
                pass

        if self.has_option(host, 'port'):
            port = int(self._credentials.get(host, 'port'))

        return hostname, port

    @staticmethod
    def _create_url(*parts: AnyStr) -> str:
        # Cast to string to ensure that all parts have the same type.
        return urlunsplit(tuple(str(part) for part in parts))

    def _get_web_protocol(self, host: str, scheme: str,
                          default_scheme: str = 'http') -> str:
        # Retrieve the protocol to use to send requests to the source.
        # This must be either HTTP or HTTPS.
        if self.has_option(host, 'protocol'):
            scheme = self._credentials.get(host, 'protocol')
        if scheme not in self.HTTP_PROTOCOLS:
            scheme = default_scheme

        return scheme

    def _format_ssh_url(self, hostname: str, auth: str, port: Optional[int],
                        path: str) -> str:
        if hostname.startswith('-'):
            raise ValueError('Long SSH host may not begin with dash')

        netloc = f'{auth}:{port}' if port is not None else auth
        return f'{self.SSH_PROTOCOL}://{netloc}{path}'

    @classmethod
    def _format_host_section(cls, parts: SplitResult) -> str:
        if parts.hostname is None:
            return ''

        if parts.port is None:
            return parts.hostname

        return f'{parts.hostname}:{parts.port}'

    def _get_username(self, protocol: str, host: str, orig_parts: SplitResult) -> Optional[str]:
        # Order of preference:
        # - Protocol-specific username configured in credentials for the host
        # - Username configured in credentials for the host
        # - Username as provided in the original URL
        # If the username was configured in the credentials (the key exists in
        # the configuration), but it has a falsy value, then the original
        # username is used.
        key = f'username.{protocol}'
        username: Optional[str] = None
        if self._credentials.has_option(host, key):
            username = self._credentials.get(host, key)
        elif self._credentials.has_option(host, 'username'):
            username = self._credentials.get(host, 'username')

        if not Configuration.has_value(username):
            username = orig_parts.username

        return username

    def _update_ssh_credentials(self, host: str, orig_parts: SplitResult) -> None:
        # Use SSH (ssh://user@host:port/path).
        username = self._get_username('ssh', host, orig_parts)
        if username is None:
            return

        # Parse the host parts and potentially follow host changes.
        hostname, port = self._get_host_parts(host, orig_parts)

        # If 'env' is given, set a credentials path to an identity key.
        if self.has_option(host, 'env'):
            credentials_env = self._credentials.get(host, 'env')
            self.credentials_path = os.getenv(credentials_env)

        auth = f'{username}{"@"}{hostname}'
        path = orig_parts.path

        # If 'strip' exists, then this value is stripped from the
        # beginning of the path if the original protocol is HTTP/HTTPS.
        if orig_parts.scheme in self.HTTP_PROTOCOLS and self.has_option(host, 'strip'):
            strip = self._credentials.get(host, 'strip')
            if path.startswith(strip):
                path = path[len(strip):]
            elif path.startswith(f'/{strip}'):
                path = path[len(strip)+1:]

        self._url = self._format_ssh_url(hostname, auth, port, path)

    def _update_http_credentials(self, host: str, orig_parts: SplitResult) -> None:
        # Use HTTP(s) (http://username:password@host:port/path).
        username = self._get_username('http', host, orig_parts)
        if username is None:
            return

        # Parse the host parts and potentially follow host changes.
        hostname, port = self._get_host_parts(host, orig_parts)

        # Add a password to the URL for basic authentication.
        password = quote(self._credentials.get(host, 'password'))

        full_host = f'{username}:{password}{"@"}{hostname}'
        if port is not None:
            full_host = f'{full_host}:{port}'

        self._url = self._create_url(orig_parts.scheme, full_host,
                                     orig_parts.path, orig_parts.query,
                                     orig_parts.fragment)

    def _update_credentials(self) -> Tuple[SplitResult, str]:
        # Update the URL of a source when hosts change, and add any additional
        # credentials to the URL or source registry.
        orig_parts = urlsplit(self._plain_url)
        host = self._format_host_section(orig_parts)

        if self._credentials.has_section(host):
            # Additional authentication options depending on protocol to use
            if orig_parts.scheme == self.SSH_PROTOCOL or self.has_option(host, 'env'):
                self._update_ssh_credentials(host, orig_parts)
            elif orig_parts.scheme in self.HTTP_PROTOCOLS and self.has_option(host, 'password'):
                self._update_http_credentials(host, orig_parts)

        return orig_parts, host

    @property
    def plain_url(self) -> str:
        """
        Retrieve the URL as it is defined for the source.

        This does not contain changes to hosts or additions of credentials.
        """

        return self._plain_url

    @property
    def web_url(self) -> Optional[str]:
        """
        Retrieve the URL for the source containing a human-readable site
        describing this specific source.

        If no such site is available, then `None` is returned.
        """

        return None

    @property
    def type(self) -> str:
        """
        Retrieve the literal type of the source, as it was initially defined.
        Note that some source classes register themselves for more than one type
        and there may be multiple classes registered for the same type.
        """

        return self._type

    @property
    def url(self) -> str:
        """
        Retrieve the final URL, after following host changes and including
        credentials where applicable
        """

        return self._url

    @property
    def name(self) -> str:
        """
        Retrieve the name of the source.

        This is a potentially human-readable name of the source, but should be
        valid for use as an identifier, altough it may be non-unique and
        different between different source data.
        """

        return self._name

    @property
    def environment(self) -> Optional[Hashable]:
        """
        Retrieve an indicator of the environment that the source lives in.

        The environment is a shared signature with other Source objects that
        are situated on the same host or group. For example, Source objects that
        are retrieved using `get_sources` have this signature.

        The returned value is hashable.
        """

        return None

    @property
    def environment_type(self) -> str:
        """
        Retrieve a type name for the environment of the source.

        The type should match up with one of the registered type names of
        the sources in the environment. It can be used to normalize the type
        names of multiple sources in the same environment such that the
        environment can ideally describe all of them. This may also be used as
        a canonical type name of the source.
        """

        return self.type

    @property
    def environment_url(self) -> Optional[str]:
        """
        Retrieve a URL for the environment that the source lives in.

        The environment's URL is a human-readable site that describes the
        sources that are situated on the same host or group. For example, Source
        objects that are retrieved using `get_sources` have the same (base) URL.
        """

        return None

    @property
    def path_name(self) -> str:
        """
        Retrieve an identifier of the source that can be used as a path name.

        The path name is potentially non-unique.
        """

        return self.name

    @property
    def file_name(self) -> Optional[str]:
        """
        Retrieve an identifier of the source that can be used as a file name,
        possibly extracted from the URL.

        If the file name cannot be extracted, then this is `None`.
        """

        return None

    @property
    def repository_class(self) -> Optional[Type[Version_Control_Repository]]:
        """
        Retrieve the class that implements a version control repository pointing
        to this source.

        If this source has no repository, then this property returns `None`.
        """

        return None

    @property
    def version(self) -> str:
        """
        Retrieve relevant version information as a string for this source.

        If no version information can be obtained, then this property returns
        an empty string.
        """

        return ''

    @property
    def credentials_path(self) -> Optional[PathLike]:
        """
        Retrieve a path to a file that contains credentials for this source.

        The file may be a SSH private key, depending on the source type. The
        path is returned as a `Path` object. If there is no such file
        configured for this source, then this property returns `None`.
        """

        return self._credentials_path

    @credentials_path.setter
    def credentials_path(self, value: Optional[PathLike]) -> None:
        """
        Update the credentials path to another location.

        Note that this may set an SSH private key even though the connection is
        not using SSH.
        """

        if value is None:
            self._credentials_path = None
        else:
            self._credentials_path = Path(value)

    def get_option(self, option: str) -> Optional[str]:
        """
        Retrieve an option from the credentials configuration of the host of
        this source.

        If the option does not exist or the value is one of 'false', 'no', '-'
        or the empty string, then `None` is returned.
        """

        if self._host is None or not self.has_option(self._host, option):
            return None

        return self._credentials.get(self._host, option)

    @classmethod
    def has_option(cls, host: str, option: str) -> bool:
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

    def check_credentials_environment(self) -> bool:
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

    def get_sources(self) -> List['Source']:
        """
        Retrieve information about additional data sources from the source.

        The return value is a list of `Source` objects. It may include sources
        that are already known or even the current source. If the source does
        not provide additional source information, then an empty list is
        returned.
        """

        return [self]

    def update_identity(self, project: Project,
                        public_key: str, dry_run: bool = False) -> None:
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

    def export(self) -> Dict[str, str]:
        """
        Retrieve a dictionary that can be exported to JSON with data about
        the current source.
        """

        return {
            'type': self._type,
            'name': self._name,
            'url': self._plain_url
        }

    def __repr__(self) -> str:
        return repr(self.export())

    def __hash__(self) -> int:
        data = self.export()
        keys = sorted(data.keys())
        values = tuple(data[key] for key in keys)
        return hash(values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Source):
            return False

        return self.export() == other.export()

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)
