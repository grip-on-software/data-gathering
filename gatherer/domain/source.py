"""
Data source domain object
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import object
import configparser
import logging
import os
import re
import urllib.parse
import gitlab3
from gitlab3.exceptions import GitLabException, ResourceNotFound
from ..svn import Subversion_Repository
from ..git import Git_Repository, GitLab_Repository

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
        self._credentials_path = None

        self._url = None
        if self._plain_url is None:
            self._host = None
        else:
            self._host = self._update_credentials()[1]

    @classmethod
    def _init_credentials(cls):
        if cls._credentials is None:
            cls._credentials = configparser.RawConfigParser()
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
            if self._follow_host_change:
                host = self._get_changed_host(host)

            username = self._credentials.get(host, 'username')
            if self._credentials.has_option(host, 'env'):
                credentials_env = self._credentials.get(host, 'env')
                self._credentials_path = os.getenv(credentials_env)
                self._url = str(username + '@' + host + ':' + orig_parts.path)
            else:
                password = self._credentials.get(host, 'password')

                auth = '{0}:{1}'.format(username, password)
                full_host = auth + '@' + host

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

        The environment is a shared signature that other Source objects that
        are situated on he same host or group all have. For example, Source
        objects that are retrieved using `get_sources` have this signature.

        The returned value must be hashable.
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

    def get_option(self, option):
        """
        Retrieve an option from the credentials configuration of the host of
        this source.

        If the option does not exist, then `None` is returned.
        """

        if not self._credentials.has_option(self._host, option):
            return None

        return self._credentials.get(self._host, option)

    def get_sources(self):
        """
        Retrieve information about additional data sources from the source.

        The return value is a list of `Source` objects. It may include sources
        that are already known or even the current source. If the source does
        not provide additional source information, then an empty list is
        returned.
        """

        # pylint: disable=no-self-use
        return []

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

    def _update_credentials(self):
        orig_parts, host = super(Subversion, self)._update_credentials()

        # Remove trunk from the end of the URL
        self._url = re.sub(r'/(trunk/?)$', '', self._url)

        return orig_parts, host

@Source_Types.register('git')
class Git(Source):
    """
    Git source information
    """

    @property
    def repository_class(self):
        return Git_Repository

    @property
    def path_name(self):
        path_name = self.get_path_name(self.url)
        if path_name is None:
            return super(Git, self).path_name

        return path_name

    @classmethod
    def get_path_name(cls, url):
        """
        Retrieve the repository name from a `url` or `None` if not possible.
        """

        parts = url.split('/')
        if len(parts) <= 1:
            return None

        # Handle URLs ending in slashes
        repo = parts[-1]
        if repo == '':
            repo = parts[-2]

        # Remove .git from repository name
        return cls.remove_git_suffix(repo)

    @staticmethod
    def remove_git_suffix(repo):
        """
        Remove the '.git' suffix from a repository name as it frequently
        occurs in the URL slug of that repository.
        """

        if repo.endswith('.git'):
            repo = repo[:-len('.git')]

        return repo

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
        self._gitlab_host = None
        self._gitlab_token = None
        self._gitlab_namespace = None
        self._gitlab_group = None
        self._gitlab_path = None
        self._gitlab_api = None

        super(GitLab, self).__init__(*args, **kwargs)

    @classmethod
    def is_gitlab_url(cls, url, follow_host_change=True):
        """
        Check whether a given URL is part of a GitLab instance.
        """

        parts = urllib.parse.urlsplit(url)
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

        return cls._has_gitlab_token(host)

    @classmethod
    def _has_gitlab_token(cls, host):
        if not cls._credentials.has_option(host, 'gitlab_token'):
            return False

        return cls._credentials.get(host, 'gitlab_token') != ''

    def _update_credentials(self):
        orig_parts, host = super(GitLab, self)._update_credentials()
        orig_host = orig_parts.netloc

        # Check which group to use in the GitLab API.
        if self._credentials.has_option(orig_host, 'group'):
            self._gitlab_group = self._credentials.get(orig_host, 'group')

        # Retrieve the actual namespace of the source.
        path = orig_parts.path.lstrip('/')
        path_parts = path.split('/', 1)
        self._gitlab_namespace = path_parts[0]

        # Check whether the host was changed and a custom gitlab group exists
        # for this host change.
        if self._follow_host_change and host != orig_host:
            path = self._update_group_url(path)

        # Find the GitLab token and URL without authentication for connecting
        # to the GitLab API.
        if self._has_gitlab_token(host):
            self._gitlab_token = self._credentials.get(host, 'gitlab_token')

        self._gitlab_host = self._create_url(orig_parts.scheme, host, '', '', '')
        self._gitlab_path = urllib.parse.quote_plus(self.remove_git_suffix(path))

        return orig_parts, host

    def _update_group_url(self, repo_path):
        if self._gitlab_group is None:
            return repo_path
        if self._gitlab_namespace == self._gitlab_group:
            return repo_path

        # Parse the current URL to update its path.
        url_parts = urllib.parse.urlsplit(self._url)
        repo_path_name = repo_path.split('/', 1)[1]
        path = '{0}/{1}-{2}'.format(self._gitlab_group, self._gitlab_namespace,
                                    repo_path_name)
        self._url = self._create_url(url_parts.scheme, url_parts.netloc, path,
                                     url_parts.query, url_parts.fragment)
        return path

    @property
    def repository_class(self):
        return GitLab_Repository

    @property
    def environment(self):
        return (self._gitlab_host, self._gitlab_group, self._gitlab_namespace)

    @property
    def host(self):
        """
        Retrieve the host name with scheme part of the GitLab instance.

        This is the base URL after following host changes.
        """

        return self._gitlab_host

    @property
    def gitlab_token(self):
        """
        Retrieve the token that is used for authenticating in the GitLab API.
        """

        return self._gitlab_token

    @property
    def gitlab_group(self):
        """
        Retrieve the custom gitlab group used on the GitLab instance.

        If this is `None`, then there is no custom group for this source.
        The caller should fall back to the project long name or some other
        information it has.

        Note that this group is instance-wide, and may not actually be the group
        that this source repository is in. Instead it is used for group URL
        updates and gitlab source queries. See `gitlab_namespace` for the
        group or namespace of the source object.
        """

        return self._gitlab_group

    @property
    def gitlab_namespace(self):
        """
        Retrieve the namespace in which the source exists.
        """

        return self._gitlab_namespace

    @property
    def gitlab_path(self):
        """
        Retrieve the path used in the GitLab API. This is the final path after
        following group URL updates. The path includes the namespace, usually
        the same as the group, and the repository name.

        The path can be used in API project calls to retrieve the project by its
        unique path identifier.
        """

        return self._gitlab_path

    @property
    def gitlab_api(self):
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        if self._gitlab_api is None:
            try:
                logging.info('Setting up API for %s', self.host)
                self._gitlab_api = gitlab3.GitLab(self.host, self.gitlab_token)
            except (AttributeError, GitLabException):
                raise RuntimeError('Cannot access the GitLab API (insufficient credentials)')

        return self._gitlab_api

    def get_sources(self):
        # pylint: disable=no-member
        if self.gitlab_group is not None:
            group_name = self.gitlab_group
        else:
            group_name = self.gitlab_namespace

        group = self.gitlab_api.group(group_name)
        if not group:
            logging.warning("Could not find group '%s' on GitLab API",
                            group_name)

        # Fetch the group projects by requesting the group to the API again.
        group_repos = self.gitlab_api.group(str(group.id)).projects

        logging.info('%s has %d repos: %s', group_name, len(group_repos),
                     ', '.join([repo['name'] for repo in group_repos]))

        sources = []
        for repo_data in group_repos:
            # Retrieve the actual project from the API, to ensure it is accessible.
            try:
                project_repo = self.gitlab_api.project(str(repo_data['id']))
            except ResourceNotFound:
                logging.warning('GitLab repository %s is not accessible',
                                repo_data['name'])
                continue

            repo_name = project_repo.name
            if not project_repo.commits(limit=1):
                logging.info('Ignoring empty GitLab repository %s', repo_name)
                continue

            source = Source.from_type('gitlab', name=repo_name,
                                      url=project_repo.http_url_to_repo,
                                      follow_host_change=False)

            sources.append(source)

        return sources
