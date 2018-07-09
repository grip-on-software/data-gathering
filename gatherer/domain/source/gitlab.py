"""
GitLab source domain object.
"""

from __future__ import absolute_import
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

from gitlab import Gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError, \
    GitlabListError
from ...request import Session
from .types import Source, Source_Types
from .git import Git
from ...git.gitlab import GitLab_Repository

@Source_Types.register('gitlab')
@Source_Types.register('git',
                       lambda cls, follow_host_change=True, url=None, **data: \
                       cls.is_gitlab_url(url,
                                         follow_host_change=follow_host_change))
class GitLab(Git):
    """
    GitLab source repository.
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
        Check whether a given URL is part of a GitLab instance for which we have
        credentials.
        """

        if url is None:
            return False

        parts = urllib.parse.urlsplit(cls._alter_git_url(url))
        return cls.is_gitlab_host(cls._format_host_section(parts),
                                  follow_host_change=follow_host_change)

    @classmethod
    def is_gitlab_host(cls, host, follow_host_change=True):
        """
        Check whether a given host (without scheme part) is a GitLab host for
        which we have credentials.
        """

        cls._init_credentials()
        if follow_host_change:
            host = cls._get_changed_host(host)

        return cls._has_gitlab_token(host)

    @classmethod
    def _has_gitlab_token(cls, host):
        return cls.has_option(host, 'gitlab_token')

    def _update_credentials(self):
        orig_parts, host = super(GitLab, self)._update_credentials()
        orig_host = orig_parts.netloc

        # Check which group to use in the GitLab API.
        if self.has_option(orig_host, 'group'):
            self._gitlab_group = self._credentials.get(orig_host, 'group')

        # Retrieve the actual namespace of the source.
        path = orig_parts.path.strip('/')
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

        scheme = self._get_web_protocol(host, orig_parts.scheme)
        if self.has_option(host, 'strip'):
            # Add the stripped path to the web URL.
            host_path = self._credentials.get(host, 'strip')
        else:
            host_path = ''

        self._gitlab_host = self._create_url(scheme, host, host_path, '', '')
        self._gitlab_path = self.remove_git_suffix(path)

        self._url = self._url.rstrip('/')

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
        # Track the new namespace and use the new URL.
        self._gitlab_namespace = self._gitlab_group
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
    def environment_url(self):
        if self._gitlab_group is not None:
            return self._gitlab_host + '/' + self._gitlab_group

        return self._gitlab_host + '/' + self._gitlab_namespace

    @property
    def web_url(self):
        return self._gitlab_host + '/' + self._gitlab_path

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
        the same as the group, and the repository name. The path is URL-encoded
        for use in parameters.

        The path can be used in API project calls to retrieve the project by its
        unique path identifier.
        """

        return urllib.parse.quote_plus(self._gitlab_path)

    @property
    def gitlab_api(self):
        """
        Retrieve an instance of the GitLab API connection for the GitLab
        instance on this host.
        """

        if self._gitlab_api is None:
            unsafe = self.get_option('unsafe_hosts')
            session = Session(verify=unsafe is None)
            try:
                logging.info('Setting up API for %s', self.host)
                self._gitlab_api = Gitlab(self.host,
                                          private_token=self.gitlab_token,
                                          session=session)
                self._gitlab_api.auth()
            except (ValueError, GitlabAuthenticationError, GitlabGetError) as error:
                raise RuntimeError('Cannot access the GitLab API: {}'.format(error))

        return self._gitlab_api

    def check_credentials_environment(self):
        if self._gitlab_group is None:
            return True

        return self._gitlab_group == self._gitlab_namespace

    def get_sources(self):
        # pylint: disable=no-member
        if self.gitlab_group is not None:
            group_name = self.gitlab_group
        else:
            group_name = self.gitlab_namespace

        try:
            group = self.gitlab_api.groups.get(group_name, lazy=True)
        except (GitlabAuthenticationError, GitlabGetError):
            logging.warning('GitLab group %s is not accessible', group_name)
            return super(GitLab, self).get_sources()

        # Fetch the group projects by requesting the group to the API again.
        group_repos = group.projects.list()

        logging.info('%s has %d repos: %s', group_name, len(group_repos),
                     ', '.join([repo.name for repo in group_repos]))

        sources = []
        for project_repo in group_repos:
            repo_name = project_repo.name
            project = self.gitlab_api.projects.get(project_repo.get_id(),
                                                   lazy=True)
            try:
                if not project.commits.list(per_page=1, all=False):
                    logging.info('Ignoring empty GitLab repository %s',
                                 repo_name)
                    continue
            except (GitlabAuthenticationError, GitlabListError):
                logging.warning('GitLab repository %s is not accessible',
                                repo_name)
                continue

            source = Source.from_type('gitlab', name=repo_name,
                                      url=project_repo.http_url_to_repo,
                                      follow_host_change=False)

            sources.append(source)

        return sources

    def update_identity(self, project, public_key, dry_run=False):
        if self.gitlab_token is None:
            raise RuntimeError('GitLab source {} has no API token'.format(self.host))

        title = 'GROS agent for the {} project'.format(project.key)
        logging.info('Checking for old SSH keys of %s from GitLab instance %s...',
                     title, self.host)

        for key in self.gitlab_api.user.keys.list(as_list=False):
            if key.title == title:
                if key.key == public_key:
                    logging.info('SSH key already exists on GitLab instance %s.',
                                 self.host)
                    return
                elif not dry_run:
                    key.delete()

        logging.info('Adding new SSH key to GitLab instance %s...', self.host)
        if not dry_run:
            self.gitlab_api.user.keys.create({
                'title': title,
                'key': public_key
            })
