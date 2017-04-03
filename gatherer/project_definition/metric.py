"""
Utilities for comparing and analyzing metric options.
"""

from builtins import object
import json

class Metric_Difference(object):
    """
    Class that determines whether metric options were changed.
    """

    def __init__(self, project, previous_targets=None):
        self._project_key = project.export_key
        if previous_targets is not None:
            self._previous_metric_targets = previous_targets
        else:
            self._previous_metric_targets = {}

        self._unique_versions = []
        self._unique_metric_targets = []

    def add_version(self, version, metric_targets):
        """
        Check whether this version contains unique changes.
        """

        # Detect whether the metrics and definitions have changed
        if metric_targets != self._previous_metric_targets:
            self._unique_versions.append(version)
            for name, metric_target in metric_targets.items():
                if name in self._previous_metric_targets:
                    previous_metric_target = self._previous_metric_targets[name]
                else:
                    previous_metric_target = {}

                if metric_target != previous_metric_target:
                    unique_target = dict(metric_target)
                    unique_target['name'] = name
                    unique_target['revision'] = version['version_id']
                    self._unique_metric_targets.append(unique_target)

            self._previous_metric_targets = metric_targets

    def export(self):
        """
        Save the unique data to JSON files.
        """

        with open(self._project_key + '/data_metric_versions.json', 'w') as out:
            json.dump(self._unique_versions, out, indent=4)

        with open(self._project_key + '/data_metric_targets.json', 'w') as out:
            json.dump(self._unique_metric_targets, out, indent=4)

    @property
    def previous_metric_targets(self):
        """
        Retrieve the previous metric targets, which need to be retained for
        later instances of this class.
        """

        return self._previous_metric_targets

    @property
    def unique_versions(self):
        """
        Retrieve the unique versions that have changed metric targets.
        """

        return self._unique_versions

    @property
    def unique_metric_targets(self):
        """
        Retrieve metric targets that changed within revisions.
        """

        return self._unique_metric_targets
