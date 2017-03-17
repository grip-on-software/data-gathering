"""
Base module that defines an abstract version control system.
"""

import json
import logging
import os.path
from .utils import Sprint_Data

class Repositories_Holder(object):
    """
    Abstract interface for interacting with multiple version control systems
    of a certain source type at once.
    """

    def __init__(self, project, repo_directory):
        self._project = project
        self._repo_directory = os.path.join(repo_directory, project.key)
        self._sprints = Sprint_Data(project)

        self._latest_versions = {}

        filename = 'vcs_versions.json'
        self._latest_filename = os.path.join(project.export_key,
                                             'latest_{}'.format(filename))
        self._export_filename = os.path.join(project.export_key,
                                             'data_{}'.format(filename))

    def _load_latest_versions(self):
        """
        Load the information detailing the latest commits from the data store.
        """

        if os.path.exists(self._latest_filename):
            with open(self._latest_filename, 'r') as latest_versions_file:
                self._latest_versions = json.load(latest_versions_file)

        return self._latest_versions

    def get_repositories(self):
        """
        Retrieve repository objects for all involved version control systems.

        Returns a generator that can be iterated over.
        """

        for source in self._project.sources:
            repo_class = source.repository_class
            path = os.path.join(self._repo_directory, source.path_name)
            repo = repo_class.from_url(source.name, path, source.url,
                                       sprints=self._sprints,
                                       credentials_path=source.credentials_path)

            if not repo.is_empty():
                yield repo

    def process(self):
        """
        Perform all actions required for retrieving the commit data of all
        the repositories and exporting it to JSON.
        """

        self._load_latest_versions()

        data = []
        for repo in self.get_repositories():
            repo_name = repo.repo_name
            logging.info('Processing repository %s', repo_name)
            if repo.repo_name in self._latest_versions:
                latest_version = self._latest_versions[repo.repo_name]
            else:
                latest_version = None

            data.extend(repo.get_versions(from_revision=latest_version))
            self._latest_versions[repo.repo_name] = repo.get_latest_version()

        self._export(data)

    def _export(self, data):
        """
        Export the version metadata and latest version identifer to JSON files.
        """

        with open(self._export_filename, 'w') as data_file:
            json.dump(data, data_file, indent=4)

        with open(self._latest_filename, 'w') as latest_versions_file:
            json.dump(self._latest_versions, latest_versions_file)

class Version_Control_Repository(object):
    """
    Abstract repository interface for a version control system.
    """

    def __init__(self, repo_name, repo_directory, sprints=None, stats=True,
                 **kwargs):
        self._repo_name = repo_name
        self._repo_directory = repo_directory

        self._sprints = sprints
        self._retrieve_stats = stats
        self._options = kwargs

    @classmethod
    def from_url(cls, repo_name, repo_directory, url, **kwargs):
        """
        Retrieve a repository handle from an external URL.

        Optionally, the repository is stored locally within a certain directory
        under `repo_directory`.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @property
    def repo(self):
        """
        Property that retrieves the back-end repository interface (lazy-loaded).
        """

        raise NotImplementedError("Must be implemented by subclass")

    @repo.setter
    def repo(self, repo):
        """
        Property that changes the back-end repository interface.

        The subclass may enforce type restrictions on the back-end object.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @property
    def repo_name(self):
        """
        Retrieve a descriptive name of the repository.
        """

        return self._repo_name

    @property
    def repo_directory(self):
        """
        Retrieve the repository directory of this version control system.

        The directory may be a local checkout or data store of the repository.
        """

        return self._repo_directory

    @property
    def retrieve_stats(self):
        """
        Check wether the metadata-retrieving methods should also retrieve
        file difference statistics from the repository.
        """

        return self._retrieve_stats

    def exists(self):
        """
        Check if the repository exists.
        """

        raise NotImplementedError("Must be implemented by subclass")

    def is_empty(self):
        """
        Check if the repository has no versions.
        """

        raise NotImplementedError("Must be implemented by subclass")

    def get_latest_version(self):
        """
        Retrieve the identifier of the latest version within the version
        control repository.
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

    def _get_sprint_id(self, commit_datetime):
        if self._sprints is not None:
            sprint_id = self._sprints.find_sprint(commit_datetime)
            if sprint_id is not None:
                return str(sprint_id)

        return str(0)
