"""
Git source domain object.
"""

import re
from .types import Source, Source_Types
from ...git import Git_Repository

@Source_Types.register('git')
class Git(Source):
    """
    Git source repository.
    """

    GIT_URL_REGEX = re.compile(r'(?P<netloc>[^@]+@[^:]+):/?(?P<path>.+)')

    @classmethod
    def _alter_git_url(cls, url):
        # Normalize git suffix
        if url.endswith('.git/'):
            url = url.rstrip('/')

        # Convert short SCP-like URLs to full SSH protocol URLs so that the
        # parsing done by the superclass can completely understand the URL.
        match = cls.GIT_URL_REGEX.match(url)
        if match:
            return 'ssh://{netloc}/{path}'.format(**match.groupdict())

        return url

    def _update_credentials(self):
        self._plain_url = self._alter_git_url(self._plain_url)
        return super(Git, self)._update_credentials()

    def _format_ssh_url(self, hostname, auth, port, path):
        # Use either short SCP-like URL or long SSH URL
        if port is not None:
            return super(Git, self)._format_ssh_url(hostname, auth, port, path)

        return '{0}:{1}'.format(auth, path)

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

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
