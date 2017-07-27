"""
GitHub source domain object.
"""

from __future__ import absolute_import
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

try:
    import urllib.parse
except ImportError:
    raise

import logging
import github
from .types import Source, Source_Types
from .git import Git
from ...git.github import GitHub_Repository

@Source_Types.register('github')
@Source_Types.register('git',
                       lambda cls, **source_data: \
                            cls.is_github_url(source_data['url']))
class GitHub(Git):
    """
    GitHub source repository.
    """

    def __init__(self, *args, **kwargs):
        self._github_token = None
        self._github_api = None
        self._github_api_url = github.MainClass.DEFAULT_BASE_URL
        self._github_owner = None
        self._github_repo = kwargs.pop('github_repo', None)
        self._github_team = kwargs.pop('github_team', None)

        super(GitHub, self).__init__(*args, **kwargs)

    @classmethod
    def is_github_url(cls, url):
        """
        Check whether a given URL is part of a GitHub instance for which we have
        credentials.
        """

        parts = urllib.parse.urlsplit(url)
        return cls.is_github_host(parts.netloc)

    @classmethod
    def is_github_host(cls, host):
        """
        Check whether a given host (without scheme part) is a GitHub host for
        which we have credentials.
        """

        cls._init_credentials()
        return cls._has_github_token(host)

    @classmethod
    def _has_github_token(cls, host):
        return cls.has_option(host, 'github_token')

    def _update_credentials(self):
        orig_parts, host = super(GitHub, self)._update_credentials()

        # Retrieve the owner from the URL of the source.
        path = orig_parts.path.lstrip('/')
        path_parts = path.split('/', 1)
        self._github_owner = path_parts[0]

        if self._has_github_token(host):
            self._github_token = self._credentials.get(host, 'github_token')
        if self.has_option(host, 'github_api_url'):
            self._github_api_url = self._credentials.get(host, 'github_api_url')

        return orig_parts, host

    @property
    def repository_class(self):
        return GitHub_Repository

    @property
    def environment(self):
        return (self._host, self.github_owner, self.github_team)

    @property
    def github_token(self):
        """
        Retrieve the token that is used for authenticating in the GitHub API.
        """

        return self._github_token

    @property
    def github_owner(self):
        """
        Retrieve the user or organization which owns source's repository.
        """

        return self._github_owner

    @property
    def github_team(self):
        """
        Retrieve the team that manages this source's repository, or `None` if
        there is no team known.
        """

        return self._github_team

    @property
    def github_repo(self):
        """
        Retrieve the repository information from the GitHub API for this
        source's repository.
        """

        if self._github_repo is None:
            full_path = '{}/{}'.format(self._github_owner, self.path_name)
            self._github_repo = self.github_api.get_repo(full_path)

        return self._github_repo

    @property
    def github_api(self):
        """
        Retrieve an instance of the GitHub API connection.
        """

        if self._github_api is None:
            logging.info('Setting up GitHub API')
            self._github_api = github.Github(self.github_token,
                                             base_url=self._github_api_url)

        return self._github_api

    def get_sources(self):
        if self._github_team is None:
            user = self.github_api.get_user(self._github_owner)
            repos = user.get_repos()
        else:
            org = self.github_api.get_organization(self._github_owner)
            team = None
            for team in org.get_teams():
                if team.slug == self._github_team:
                    break
            else:
                msg = "Cannot find team '{}' in organization '{}'"
                raise RuntimeError(msg.format(self._github_team,
                                              self._github_owner))

            repos = team.get_repos()

        sources = []
        for repo in repos:
            source = Source.from_type('github',
                                      name=repo.name,
                                      url=repo.clone_url,
                                      github_team=self._github_team,
                                      github_repo=repo)
            sources.append(source)

        return sources

    def export(self):
        data = super(GitHub, self).export()
        data['github_team'] = self._github_team

        return data
