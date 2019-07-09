"""
Base module that defines an abstract version control system.
"""

import json
import logging
from pathlib import Path, PurePath
from .repo import RepositorySourceException, RepositoryDataException
from ..table import Table
from ..utils import Sprint_Data

class Repositories_Holder:
    """
    Abstract interface for interacting with multiple version control systems
    of a certain source type at once.
    """

    def __init__(self, project, repo_directory):
        self._project = project
        self._repo_directory = PurePath(repo_directory, project.key)
        self._sprints = Sprint_Data(project)

        self._latest_versions = {}
        self._latest_filename = self._make_tracker_path('latest_vcs_versions')
        self._update_trackers = {}

    def _make_tracker_path(self, file_name):
        return Path(self._project.export_key, f'{file_name}.json')

    def _load_latest_versions(self):
        """
        Load the information detailing the latest commits from the data store.
        """

        if self._latest_filename.exists():
            with self._latest_filename.open('r') as latest_versions_file:
                self._latest_versions = json.load(latest_versions_file)

        return self._latest_versions

    def _load_update_tracker(self, file_name):
        if file_name in self._update_trackers:
            return self._update_trackers[file_name]

        path = self._make_tracker_path(file_name)
        if path.exists():
            with path.open('r') as update_file:
                self._update_trackers[file_name] = json.load(update_file)
        else:
            self._update_trackers[file_name] = {}

        return self._update_trackers[file_name]

    def _check_update_trackers(self, repo, repo_name):
        for file_name in repo.update_trackers.keys():
            update_tracker = self._load_update_tracker(file_name)
            if repo_name in update_tracker:
                repo.set_update_tracker(file_name, update_tracker[repo_name])

    def _check_up_to_date(self, source, repo_class):
        # Check up-to-dateness before retrieving from source.
        # Note that this excludes the entire repository from the gathering
        # process if it is considered up to date, which might also mean
        # that auxiliary table data is not retrieved. Repository classes
        # must override is_up_to_date to support auxliary data updates.
        #
        # This check if performed by `get_repositories` before including the
        # repository in the update/retrieve cycle, but is skipped if its `pull`
        # parameter is disabled.
        if source.name in self._latest_versions:
            latest_version = self._latest_versions[source.name]
            update_tracker = None
            if repo_class.UPDATE_TRACKER_NAME is not None:
                data = self._load_update_tracker(repo_class.UPDATE_TRACKER_NAME)
                if source.name in data:
                    update_tracker = data[source.name]

            try:
                if repo_class.is_up_to_date(source, latest_version,
                                            update_tracker=update_tracker):
                    logging.info('Repository %s: Already up to date.',
                                 source.name)
                    return True
            except RepositorySourceException:
                return False

        return False

    @staticmethod
    def _init_tables(repo_class, tables):
        for table_name in repo_class.AUXILIARY_TABLES:
            if table_name not in tables:
                tables[table_name] = []

    def get_repositories(self, tables, force=False, pull=True):
        """
        Retrieve repository objects for all involved version control systems.

        Repositories that are up to date (if it can be determined beforehand)
        and repositories that are empty are not retrieved. Repositories that
        cannot be updated or retrieved are skipped unless `force` is given and
        the repository can be retrieved in full instead of updating from the
        working directory. The `force` option removes working directories that
        encounter problems to achieve this. The `pull` option allows skipping
        local updates of the repository while still obtaining the current
        versions as well as any auxiliary data.

        Returns a generator that can be iterated over.
        """

        for source in self._project.sources:
            repo_class = source.repository_class

            # Check if the source has version control repository functionality.
            if repo_class is None:
                continue

            self._init_tables(repo_class, tables)

            if pull and self._check_up_to_date(source, repo_class):
                continue

            path = PurePath(self._repo_directory, source.path_name)
            try:
                repo = repo_class.from_source(source, path,
                                              project=self._project,
                                              sprints=self._sprints,
                                              force=force,
                                              pull=pull)
            except RepositorySourceException:
                logging.exception('Cannot retrieve repository source for %s',
                                  source.name)
                continue

            self._check_update_trackers(repo, source.name)

            if not repo.is_empty():
                yield repo

    def process(self, force=False, pull=True):
        """
        Perform all actions required for retrieving updated commit data of all
        the repositories and exporting it to JSON. If `force` is set to `True`,
        then repositories that cannot be updated can be deleted locally and
        retrieved. If `pull` is set to `False`, then repositories are not
        updated locally is there already is a local state of the repository
        at the appropriate directory location.
        """

        self._load_latest_versions()

        encrypt_fields = ('developer', 'developer_username', 'developer_email')
        versions = Table('vcs_versions', encrypt_fields=encrypt_fields)
        tables = {}
        for repo in self.get_repositories(tables, force=force, pull=pull):
            try:
                self._process_repo(repo, versions, tables, force=force)
            except (RepositorySourceException, RepositoryDataException):
                logging.exception('Cannot retrieve repository data for %s',
                                  repo.repo_name)
                if force and repo.repo_name in self._latest_versions:
                    del self._latest_versions[repo.repo_name]

        self._export(versions, tables)

    def _process_repo(self, repo, versions, tables, force=False):
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
        skip_stats = repo.source.get_option('skip_stats')
        versions.extend(repo.get_data(from_revision=latest_version, force=force,
                                      stats=not skip_stats))
        self._latest_versions[repo.repo_name] = repo.get_latest_version()
        for table_name, table_data in repo.tables.items():
            tables[table_name].extend(table_data.get())

        # Keep the new values of the auxiliary update trackers.
        for file_name, value in repo.update_trackers.items():
            if file_name not in self._update_trackers:
                self._load_update_tracker(file_name)

            self._update_trackers[file_name][repo.repo_name] = value

    def _export(self, versions, tables):
        """
        Export the version metadata, additional table metadata, and identifiers
        of the latest versions from the repositories to JSON files.
        """

        versions.write(self._project.export_key)

        for table, table_data in tables.items():
            table_path = Path(self._project.export_key, f'data_{table}.json')
            with table_path.open('w') as table_file:
                json.dump(table_data, table_file, indent=4)

        with self._latest_filename.open('w') as latest_versions_file:
            json.dump(self._latest_versions, latest_versions_file)

        for file_name, repo_trackers in self._update_trackers.items():
            with self._make_tracker_path(file_name).open('w') as tracker_file:
                json.dump(repo_trackers, tracker_file)
