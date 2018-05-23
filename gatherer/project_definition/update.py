"""
Utilities for tracking updates between versions of a project definition.
"""

from builtins import object
import json
import os
from ..domain.sources import Sources

class Update_Tracker(object):
    """
    Class that keeps track of the previous and current state of an incremental
    update, so that the data gatherer can resume from a previous known state.
    """

    def __init__(self, project, target='metric_options'):
        self._project = project
        self._source = project.project_definitions_source

        export_key = project.export_key
        self._filename = os.path.join(export_key, '{}_update.json'.format(target))

        self._file_loaded = False
        self._previous_data = None
        self._sources = Sources()
        self._versions = {}

    def get_start_revision(self, from_revision=None):
        """
        Retrieve the revision from which we should retrieve new versions from.

        By default, this is the last revision that was parsed previously from
        this specific source, but this can be overridden using `from_revision`.
        """

        if from_revision is not None:
            return from_revision

        self._read()

        if self._sources.has_url(self._source.url):
            return self._versions[self._source.plain_url]

        return None

    def get_previous_data(self):
        """
        Retrieve the metadata retrieved from the latest unique revision that was
        parsed previously.
        """

        self._read()

        if self._previous_data is None:
            return {}

        return self._previous_data

    def _read(self):
        if self._file_loaded:
            return

        if os.path.exists(self._filename):
            with open(self._filename, 'r') as update_file:
                data = json.load(update_file)

            self._previous_data = data['targets']
            if 'sources' in data:
                self._sources.load_sources(data['sources'])
                self._versions = data['versions']

        self._file_loaded = True

    def set_end(self, end_revision, previous_data):
        """
        Store the new current state of the data retrieval from the project
        definitions from the source. `end_revision` is the latest revision
        that was parsed in this run, or `None` if no revisions were parsed.
        `previous_data` is a serializable object to compare against for checking
        if the next update has changes.
        """

        if end_revision is None:
            # Mark as up to date to this time.
            os.utime(self._filename, None)
        else:
            self._read()

            if not self._sources.has_url(self._source.url):
                self._sources.add(self._source)

            self._versions[self._source.plain_url] = end_revision

            data = {
                'sources': self._sources.export(),
                'versions': self._versions,
                'targets': previous_data
            }

            self._project.make_export_directory()
            with open(self._filename, 'w') as update_file:
                json.dump(data, update_file)
