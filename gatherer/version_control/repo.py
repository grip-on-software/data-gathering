"""
Base module that defines an abstract version control system repository.
"""

from builtins import str
from builtins import object
from enum import Enum, unique
import logging

class RepositorySourceException(RuntimeError):
    """
    Exception that indicates that a call that updates the local states of the
    repository from its source has failed due to source problems.
    """

    pass

class FileNotFoundException(RuntimeError):
    """
    Exception that indicates that a `Version_Control_Repository.get_contents`
    call failed due to an invalid or missing file.
    """

    pass

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

    # A single file name (without the .json extension) used for update tracking
    # of auxiliary data provided by this repository.
    UPDATE_TRACKER_NAME = None

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

        If the repository cannot be obtained from the source, the method may
        raise a `RepositorySourceException`.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @classmethod
    def is_up_to_date(cls, source, latest_version, update_tracker=None):
        # pylint: disable=unused-argument
        """
        Check whether the `source` is up to date without retrieving the entire
        repository. The `latest_version` is a version identifier of the version
        that has been collected previously. Optionally, `update_tracker` is
        the update tracker value for the repository in the file referenced by
        `UPDATE_TRACKER_NAME`.

        If it is impossible to determine up-to-dateness, or the entire
        repository does not need to be retrieved beforehand to check this
        during version collection, then this class method returns `False`.

        If the source cannot be reached, then a `RepositorySourceException` may
        be raised.
        """

        return False

    @property
    def repo(self):
        """
        Property that retrieves the back-end repository interface (lazy-loaded).

        If the repository cannot be obtained, then a `RepositorySourceException`
        may be raised.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @repo.setter
    def repo(self, repo):
        """
        Property that changes the back-end repository interface.

        The subclass may enforce type restrictions on the back-end object
        and raise a `TypeError` if these are not met.
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

    def update(self, shallow=False, checkout=True):
        """
        Update the local state of the repository to its latest upstream state.

        If the repository cannot be updated, for example if it has no prior
        local state, then an exception may be raised.

        If `shallow` is `True`, then check out as few commits from the remote
        repository as possible.

        If `checkout` is `True`, then make the current state explicitly
        available. If it is `False`, then the current state files need not be
        stored explicitly on the filesystem.

        If the repository cannot be updated due to a source issue, then this
        method may raise a `RepositorySourceException`.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def checkout(self, paths=None, shallow=False):
        """
        Create a local state of the repository based on the current uptream
        state or a part of it.

        If the local state cannot be created, for example if it already exists,
        then an exception may be raised. The argument `paths` may be a list of
        directory paths to check out in the repository local state. The local
        repository should either be a complete checkout or contain at least
        these path patterns.

        If `shallow` is `True`, then check out as few commits from the remote
        repository as possible.

        If the repository cannot be updated due to a source issue, then this
        method may raise a `RepositorySourceException`.
        """

        raise NotImplementedError('Must be implemented by subclass')

    def checkout_sparse(self, paths, remove=False, shallow=False):
        """
        Update information and checked out files in the local state of the
        repository such that it also contains the given list of `paths`.

        The resulting state has the new paths and they are up to date with
        the remote state of the repository.

        If `remove` is `True`, then instead of adding the new paths to the local
        state, they are removed from the local state if they existed.
        Additionally, the 'excluded' state of the specific paths may be tracked
        in the local state of the repository.

        If `shallow` is `True`, then check out as few commits from the remote
        repository as possible.

        If sparse checkouts are not supported, then this method simply updates
        the (entire) repository such that all paths are up to date.

        If the repository cannot be updated due to a source issue, then this
        method may raise a `RepositorySourceException`.
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
