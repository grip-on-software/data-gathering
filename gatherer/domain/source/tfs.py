"""
Team Foundation Server domain object.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import logging
try:
    import urllib.parse
except ImportError:
    raise

from .types import Source, Source_Types
from .git import Git
from ...git.tfs import TFS_Repository, TFS_Project

@Source_Types.register('tfs')
@Source_Types.register('git',
                       lambda cls, follow_host_change=True, url=None, **data: \
                       cls.is_tfs_url(url,
                                      follow_host_change=follow_host_change))
class TFS(Git):
    """
    Team Foundation Server source repository.
    """

    def __init__(self, *args, **kwargs):
        self._tfs_host = None
        self._tfs_collections = None
        self._tfs_repo = None
        self._tfs_user = None
        self._tfs_password = None
        self._tfs_api = None

        super(TFS, self).__init__(*args, **kwargs)

    @classmethod
    def is_tfs_url(cls, url, follow_host_change=True):
        """
        Check whether a given URL is part of a TFS instance.
        """

        if url is None:
            return False

        parts = urllib.parse.urlsplit(url)
        return cls.is_tfs_host(parts.netloc,
                               follow_host_change=follow_host_change)

    @classmethod
    def is_tfs_host(cls, host, follow_host_change=True):
        """
        Check whether a given host (without scheme part) is a TFS host.
        """

        cls._init_credentials()
        if follow_host_change:
            host = cls._get_changed_host(host)

        return cls.has_option(host, 'tfs')

    def _update_credentials(self):
        orig_parts, host = super(TFS, self)._update_credentials()

        # Ensure we have a URL to the web host for API purposes.
        # This includes altering the web port to the one that TFS listens to.
        scheme = self._get_web_protocol(host, orig_parts.scheme)
        if self.has_option(host, 'web_port'):
            hostname = self._get_host_parts(host, orig_parts)[0]
            web_host = '{}:{}'.format(hostname,
                                      self._credentials.get(host, 'web_port'))
        else:
            web_host = host

        self._tfs_host = self._create_url(scheme, web_host, '', '', '')

        # Retrieve the TFS collection
        path = orig_parts.path.lstrip('/')
        path_parts = path.split('/_git/', 1)
        tfs_path = path_parts[0]
        if len(path_parts) > 1:
            self._tfs_repo = path_parts[1].rstrip('/')

        tfs_parts = tfs_path.split('/')
        num_parts = 2 if tfs_parts[0] == 'tfs' else 1
        if len(tfs_parts) > num_parts:
            collection = '/'.join(tfs_parts[:num_parts])
            self._tfs_collections = (collection, tfs_parts[num_parts])
        else:
            self._tfs_collections = (tfs_path,)

        self._tfs_user = self._credentials.get(host, 'username')
        self._tfs_password = self._credentials.get(host, 'password')

        # Remove trailing slashes since they are optional and the TFS API
        # returns remote URLs without slashes.
        self._url = self._url.rstrip('/')

        return orig_parts, host

    @property
    def repository_class(self):
        return TFS_Repository

    @property
    def environment(self):
        return (self._tfs_host,) + self._tfs_collections

    @property
    def environment_url(self):
        return self._tfs_host + '/' + '/'.join(self._tfs_collections)

    @property
    def web_url(self):
        return self.environment_url + '/' + self._tfs_repo

    @property
    def tfs_api(self):
        """
        Retrieve an instance of the TFS API connection for the TFS collection
        on this host.
        """

        if self._tfs_api is None:
            logging.info('Setting up API for %s', self._tfs_host)
            self._tfs_api = TFS_Project(self._tfs_host, self._tfs_collections,
                                        urllib.parse.unquote(self._tfs_user),
                                        self._tfs_password)

        return self._tfs_api

    @property
    def tfs_collections(self):
        """
        Retrieve the collection path and optionally project name for the source.
        The value is either a tuple with one or two elements, or `None`.
        The first element of the tuple is the collection path, joined with
        slashes, and the second element if available is the project name,
        which is left out if the collection already provides unique
        identification for the TFS project.
        """

        return self._tfs_collections

    @property
    def tfs_repo(self):
        """
        Retrieve the repository name from the TFS URL.
        """

        return self._tfs_repo

    def _format_url(self, url):
        parts = urllib.parse.urlsplit(url)
        return self._create_url(parts.scheme, self._host, parts.path,
                                parts.query, parts.fragment)

    def check_credentials_environment(self):
        tfs_collection = self.get_option('tfs')
        if tfs_collection is None or tfs_collection == 'true':
            return True

        return '/'.join(self._tfs_collections).startswith(tfs_collection)

    def get_sources(self):
        repositories = self.tfs_api.repositories()
        sources = []
        for repository in repositories:
            url = self._format_url(repository['remoteUrl'])
            source = Source.from_type('tfs', name=repository['name'], url=url,
                                      follow_host_change=False)
            sources.append(source)

        return sources
