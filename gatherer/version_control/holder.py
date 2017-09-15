"""
Base module that defines an abstract version control system.
"""

from builtins import object
import json
import logging
import os.path
from ..table import Table
from ..utils import Sprint_Data

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
        if file_name in self._update_trackers:
            return self._update_trackers[file_name]

        path = self._make_tracker_path(file_name)
        if os.path.exists(path):
            with open(path) as update_file:
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
        if source.name in self._latest_versions:
            latest_version = self._latest_versions[source.name]
            update_tracker = None
            if repo_class.UPDATE_TRACKER_NAME is not None:
                data = self._load_update_tracker(repo_class.UPDATE_TRACKER_NAME)
                if source.name in data:
                    update_tracker = data[source.name]

            if repo_class.is_up_to_date(source, latest_version,
                                        update_tracker=update_tracker):
                logging.info('Repository %s: Already up to date.',
                             source.name)
                return True

        return False

    def get_repositories(self):
        """
        Retrieve repository objects for all involved version control systems.

        Repositories that are up to date (if it can be determined beforehand)
        and repositories that are empty are not retrieved.

        Returns a generator that can be iterated over.
        """

        for source in self._project.sources:
            repo_class = source.repository_class

            # Check if the source has version control repository functionality.
            if repo_class is None:
                continue

            if self._check_up_to_date(repo_class, source):
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

        encrypt_fields = ('developer', 'developer_username', 'developer_email')
        versions = Table('vcs_versions', encrypt_fields=encrypt_fields)
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
