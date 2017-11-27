"""
Git source domain object.
"""

from .types import Source, Source_Types
from ...git import Git_Repository

@Source_Types.register('git')
class Git(Source):
    """
    Git source repository.
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

    def update_identity(self, project, public_key, dry_run=False):
        raise RuntimeError('Source does not support updating SSH key')
