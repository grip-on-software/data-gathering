"""
Base module that defines an abstract version control system.
"""

class Version_Control_Repository(object):
    """
    Abstract repository interface for a version control system.
    """

    def __init__(self, repo_name, repo_directory, stats=True):
        self.repo_name = repo_name
        self.repo_directory = repo_directory
        self.retrieve_stats = stats

    @classmethod
    def from_url(cls, repo_name, repo_directory, url):
        """
        Retrieve a repository handle from an external URL.

        Optionally, the repository is stored locally within a certain directory
        under `repo_directory`.
        """

        raise NotImplementedError("Must be implemented by subclass")

    def get_versions(self, filename='', from_revision=None, to_revision=None, descending=False):
        """
        Retrieve metadata about each version in the repository, or those that
        change a specific file path `filename`.

        The range of the versions to retrieve can be set with `from_revision`
        and `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default).
        """

        raise NotImplementedError("Must be implemented by subclass")
