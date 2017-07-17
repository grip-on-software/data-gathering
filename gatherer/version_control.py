"""
Base module that defines an abstract version control system.
"""

from builtins import str
from builtins import object
from enum import Enum, unique
import json
import logging
import os.path
from .table import Table
from .utils import Sprint_Data

class FileNotFoundException(RuntimeError):
    """
    Exception that indicates that a `Version_Control_Repository.get_contents`
    call failed due to an invalid or missing file.
    """

    pass

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
        self._latest_filename = self._make_tracker_path('latest_vcs_versions')
        self._update_trackers = {}

    def _make_tracker_path(self, file_name):
        return os.path.join(self._project.export_key, file_name + '.json')

    def _load_latest_versions(self):
        """
        Load the information detailing the latest commits from the data store.
        """

        if os.path.exists(self._latest_filename):
            with open(self._latest_filename, 'r') as latest_versions_file:
                self._latest_versions = json.load(latest_versions_file)

        return self._latest_versions

    def _load_update_tracker(self, file_name):
        path = self._make_tracker_path(file_name)
        if os.path.exists(path):
            with open(path) as update_file:
                self._update_trackers[file_name] = json.load(update_file)
        else:
            self._update_trackers[file_name] = {}

    def _check_update_trackers(self, repo, repo_name):
        for file_name in repo.update_trackers.keys():
            if file_name not in self._update_trackers:
                self._load_update_tracker(file_name)

            update_tracker = self._update_trackers[file_name]
            if repo_name in update_tracker:
                repo.set_update_tracker(file_name, update_tracker[repo_name])

    def get_repositories(self):
        """
        Retrieve repository objects for all involved version control systems.

        Repositories that are up to date (if it can be determined beforehand)
        and repositories that are empty are not retrieved.

        Returns a generator that can be iterated over.
        """

        for source in self._project.sources:
            repo_class = source.repository_class

            # Check up-to-dateness before retrieving from source
            # Note that this excludes the entire repository from the gathering
            # process if it is considered up to date, which might also mean
            # that auxiliary table data is not retrieved.
            if source.name in self._latest_versions:
                latest_version = self._latest_versions[source.name]
                if repo_class.is_up_to_date(source, latest_version):
                    logging.info('Repository %s: Already up to date.',
                                 source.name)
                    continue

            path = os.path.join(self._repo_directory, source.path_name)
            repo = repo_class.from_source(source, path, project=self._project,
                                          sprints=self._sprints)

            self._check_update_trackers(repo, source.name)

            if not repo.is_empty():
                yield repo

    def process(self):
        """
        Perform all actions required for retrieving the commit data of all
        the repositories and exporting it to JSON.
        """

        self._load_latest_versions()

        versions = Table('vcs_versions',
                         encrypt_fields=('developer', 'developer_email'))
        tables = {}
        for repo in self.get_repositories():
            # Retrieve all tables from the repositories so that we know the
            # names and overwrite old export files when there are no updates.
            for table_name, table_data in repo.tables.items():
                if table_name not in tables:
                    tables[table_name] = []

            repo_name = repo.repo_name
            logging.info('Processing repository %s', repo_name)
            if repo.repo_name in self._latest_versions:
                latest_version = self._latest_versions[repo.repo_name]
            else:
                latest_version = None

            # Retrieve the versions and auxliary tables.
            versions.extend(repo.get_data(from_revision=latest_version))
            self._latest_versions[repo.repo_name] = repo.get_latest_version()
            for table_name, table_data in repo.tables.items():
                tables[table_name].extend(table_data.get())

            # Keep the new values of the auxiliary update trackers.
            for file_name, value in repo.update_trackers.items():
                if file_name not in self._update_trackers:
                    self._load_update_tracker(file_name)

                self._update_trackers[file_name][repo.repo_name] = value

        self._export(versions, tables)

    def _export(self, versions, tables):
        """
        Export the version metadata, additional table metadata, and identifiers
        of the latest versions from the repositories to JSON files.
        """

        versions.write(self._project.export_key)

        for table, table_data in tables.items():
            table_filename = os.path.join(self._project.export_key,
                                          'data_{}.json'.format(table))
            with open(table_filename, 'w') as table_file:
                json.dump(table_data, table_file, indent=4)

        with open(self._latest_filename, 'w') as latest_versions_file:
            json.dump(self._latest_versions, latest_versions_file)

        for file_name, repo_trackers in self._update_trackers.items():
            with open(self._make_tracker_path(file_name), 'w') as tracker_file:
                json.dump(repo_trackers, tracker_file)

@unique
class Change_Type(Enum):
    # pylint: disable=too-few-public-methods
    """
    Known types of changes that are made to files in version control
    repositories. The enum values are shorthand labels for the change type.
    """

    MODIFIED = 'M'
    ADDED = 'A'
    DELETED = 'D'
    REPLACED = 'R'

    @classmethod
    def from_label(cls, label):
        """
        Retrieve a change type from its shorthand label.
        """

        for entity in cls:
            if entity.value == label[0]:
                return entity

        raise ValueError('Label {} is not a valid change type'.format(label))

class Version_Control_Repository(object):
    """
    Abstract repository interface for a version control system.
    """

    def __init__(self, source, repo_directory, sprints=None, project=None,
                 **kwargs):
        if kwargs:
            logging.debug('Unused repository arguments: %r', kwargs)

        self._source = source
        self._repo_name = source.name
        self._repo_directory = repo_directory

        self._sprints = sprints
        self._project = project

        self._tables = {}
        self._update_trackers = {}

    @classmethod
    def from_source(cls, source, repo_directory, **kwargs):
        """
        Retrieve a repository handle from a `Source` domain object.

        This class method may initialize the repository differently, for example
        by retrieving the latest versions or keeping the repository remotely.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @classmethod
    def is_up_to_date(cls, source, latest_version):
        # pylint: disable=unused-argument
        """
        Check whether the `source` is up to date without retrieving the entire
        repository. The `latest_version` is a version identifier of the version
        that has been collected previously.

        If it is impossible to determine up-to-dateness, or the entire
        repository does not need to be retrieved beforehand to check this
        during version collection, then this class method returns `False`.
        """

        return False

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
    def source(self):
        """
        Retrieve the Source object describing the repository.
        """

        return self._source

    @property
    def project(self):
        """
        Retrieve the `Project` domain object for this repository, in case the
        repository is known to belong to a project. Otherwise, this property
        returns `None`.
        """

        return self._project

    @property
    def version_info(self):
        """
        Retrieve a tuple of the repository back-end interface used.

        This tuple contains major, minor and any additional version numbers as
        integers, which can be compared against other tuples us such integers.
        """

        raise NotImplementedError("Must be implemented by subclasses")

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

    def update(self):
        """
        Update the local state of the repository to its latest upstream state.

        If the repository cannot be updated, for example if it has no prior local state, then
        an exception may be raised.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def checkout(self, paths=None):
        """
        Create a local state of the repository based on the current uptream
        state or a part of it.

        If the local state cannot be created, for example if it already exists,
        then an exception may be raised. The argument `paths` may be a list of
        directory paths to check out in the repository local state. The local
        repository should either be a complete checkout or contain at least
        these path patterns.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def checkout_sparse(self, paths, remove=False):
        """
        Update information and checked out files in the local state of the
        repository such that it also contains the given list of `paths`.

        The resulting state has the new paths and they are up to date with
        the remote state of the repository.

        If `remove` is `True`, then instead of adding the new paths to the local
        state, they are removed from the local state if they existed.
        Additionally, the 'excluded' state of the specific paths may be tracked
        in the local state of the repository.

        If sparse checkouts are not supported, then this method simply updates
        the (entire) repository such that all paths are up to date.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def get_latest_version(self):
        """
        Retrieve the identifier of the latest version within the version
        control repository.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @property
    def tables(self):
        """
        Retrieve additional metadata of the repository that was obtained during
        source initialization or version searches.

        The data from each table, keyed by its name, is a list of dictionaries
        with at least the repository name and other identifiers it relates to.
        """

        return self._tables

    @property
    def update_trackers(self):
        """
        Retrieve a dictionary of update tracker values.

        The keys of the dictionary are file names to use for the update files,
        excluding the path and JSON extension. The values are simple
        serializable values that the repository object can use in another run
        to determine what data it should collect.
        """

        return self._update_trackers.copy()

    def set_update_tracker(self, file_name, value):
        """
        Change the current value of an update tracker.
        """

        if file_name not in self._update_trackers:
            raise KeyError("File name '{}' is not registered as update tracker".format(file_name))

        self._update_trackers[file_name] = value

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        version `revision`, or the current version if not given.

        If the contents cannot be retrieved due to a missing or invalid file,
        then this method raises a `FileNotFoundException`.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def get_versions(self, filename='', from_revision=None, to_revision=None,
                     descending=False, **kwargs):
        """
        Retrieve metadata about each version in the repository, or those that
        change a specific file path `filename`.

        The range of the versions to retrieve can be set with `from_revision`
        and `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default).

        An additional argument may be `stats`, which determines whether to
        retrieve file difference statistics from the repository. This argument
        and other VCS-specific arguments are up to the called method to adhere.
        """

        raise NotImplementedError("Must be implemented by subclass")

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        """
        Retrieve version and auxiliary data from the repository.
        """

        return self.get_versions(from_revision=from_revision,
                                 to_revision=to_revision, **kwargs)

    def _parse_version(self, commit, stats=True, **kwargs):
        """
        Internal method to parse information retrieved from the back end into
        a dictionary of version information. `commit` is a generic object with
        properties specific to the VCS. `stats` indicates whether we should
        also fill the dictionary with difference statistics and populate tables
        with auxiliary data.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    def _get_sprint_id(self, commit_datetime):
        if self._sprints is not None:
            sprint_id = self._sprints.find_sprint(commit_datetime)
            if sprint_id is not None:
                return str(sprint_id)

        return str(0)
