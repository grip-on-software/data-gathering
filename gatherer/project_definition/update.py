"""
Utilities for tracking updates between versions of a project definition.
"""

import json
import os

class Update_Tracker(object):
    """
    Class that keeps track of the previous and current state of an incremental
    update, so that the data gatherer can resume from a previous known state.
    """

    def __init__(self, project_key):
        self._project_key = project_key
        self._filename = self._project_key + '/metric_options_update.json'

        self._file_loaded = False
        self._from_revision = None
        self._previous_targets = None

    def get_start_revision(self, from_revision=None):
        """
        Retrieve the revision from which we should retrieve new versions from.

        By default, this is the last revision that was parsed previously,
        but this can be overridden using `from_revision`.
        """

        if from_revision is not None:
            return from_revision

        if not self._file_loaded:
            self._read()

        if self._from_revision is None:
            return None

        return self._from_revision + 1

    def get_previous_targets(self):
        """
        Retrieve the metric targets of the latest unique revision that was
        parsed previously.
        """

        if not self._file_loaded:
            self._read()

        if self._previous_targets is None:
            return {}

        return self._previous_targets

    def _read(self):
        if os.path.exists(self._filename):
            with open(self._filename, 'r') as update_file:
                data = json.load(update_file)

            self._from_revision = int(data['version'])
            self._previous_targets = data['targets']

        self._file_loaded = True

    def set_end(self, end_revision, previous_targets):
        """
        Store the new current state of the data retrieval. `end_revision` is
        the latest revision that was parsed in this run, or `None` if no
        revisions were parsed. `previous_targets` is a dictionary of metric
        targets to compare against for checking if the next update has changes.
        """

        if end_revision is not None:
            data = {
                'version': end_revision,
                'targets': previous_targets
            }
            with open(self._filename, 'w') as update_file:
                json.dump(data, update_file)
