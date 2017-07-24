"""
Module that handles access to a GitHub-based repository, augmenting the usual
repository version information with pull requests and commit comments.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from .repo import Git_Repository

class GitHub_Repository(Git_Repository):
    """
    Git repository hosted by GitHub.
    """

    def __init__(self, source, repo_directory, project=None, **kwargs):
        super(GitHub_Repository, self).__init__(source, repo_directory,
                                                project=project, **kwargs)

    @property
    def api(self):
        """
        Retrieve an instance of the GitHub API connection for this source.
        """

        return self._source.github_api

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        versions = super(GitHub_Repository, self).get_data(from_revision,
                                                           to_revision,
                                                           **kwargs)

        return versions
