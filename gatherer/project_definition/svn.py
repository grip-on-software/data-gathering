"""
Module for collecting data from various versions of project definitions.
"""

import logging
from .metric import Metric_Difference
from .parser import Metric_Options_Parser, Sources_Parser
from .update import Update_Tracker
from ..domain import Source
from ..svn import Subversion_Repository

class Collector(object):
    """
    Class that collects and aggregates data from different versions of project
    definition files.
    """

    def __init__(self, project, repo_path, target='project_definition',
                 **options):
        self._project = project
        self._update_tracker = Update_Tracker(self._project, target=target)
        self._repo = Subversion_Repository('kwaliteitsmetingen', repo_path,
                                           stats=False)
        self._filename = '{}/project_definition.py'.format(project.quality_metrics_name)

        self._options = options

    @property
    def repo(self):
        """
        Retrieve the Subversion repository containing the project definitions.
        """

        return self._repo

    def collect(self, from_revision=None, to_revision=None):
        """
        Collect data from project definitions of revisions in the current range.
        """

        from_revision = self._update_tracker.get_start_revision(from_revision)
        versions = self._repo.get_versions(self._filename,
                                           from_revision=from_revision,
                                           to_revision=to_revision,
                                           descending=False)
        end_revision = None
        for version in versions:
            logging.debug('Collecting version %s', version['version_id'])
            self.collect_version(version)
            end_revision = version['version_id']

        self.finish(end_revision)

    def finish(self, end_revision, data=None):
        """
        Finish retrieving data based on the final version we collect.

        The `data` may contain additional data from this version to track
        between updates.
        """

        self._update_tracker.set_end(end_revision, data)

    def collect_version(self, version):
        """
        Collect information from a version of the project definition,
        based on a dictionary containing details of a Subversion version.
        """

        parser = self.build_parser(version)
        contents = self._repo.get_contents(self._filename,
                                           revision=version['version_id'])
        try:
            parser.load_definition(contents)
            result = parser.parse()
            self.aggregate_result(version, result)
        except RuntimeError as error:
            logging.warning("Problem with revision %s: %s",
                            version['version_id'], error.message)

    def aggregate_result(self, version, result):
        """
        Perform an action on the collected result to format it according to our
        needs.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def build_parser(self, version):
        """
        Retrieve a project definition parser object that retrieves the data that
        we collect.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class Sources_Collector(Collector):
    """
    Collector that retrieves version control sources from project definitions.
    """

    def __init__(self, project, repo_path, **kwargs):
        super(Sources_Collector, self).__init__(project, repo_path,
                                                target='project_sources',
                                                **kwargs)
        self._repo_path = repo_path

    def build_parser(self, version):
        return Sources_Parser(self._repo_path, **self._options)

    def aggregate_result(self, version, result):
        for name, metric_source in result.items():
            if 'Subversion' in metric_source:
                source = Source('subversion', name=name,
                                url=metric_source['Subversion'])
            elif 'Git' in metric_source:
                source = Source('git', name=name, url=metric_source['Git'])
            else:
                continue

            self._project.add_source(source)

class Metric_Options_Collector(Collector):
    """
    Collector that retrieves changes to metric targets from project definitions.
    """

    def __init__(self, project, repo_path, **kwargs):
        super(Metric_Options_Collector, self).__init__(project, repo_path,
                                                       target='metric_options',
                                                       **kwargs)
        self._diff = Metric_Difference(project,
                                       self._update_tracker.get_previous_data())

    def build_parser(self, version):
        return Metric_Options_Parser(file_time=version['commit_date'],
                                     **self._options)

    def aggregate_result(self, version, result):
        self._diff.add_version(version, result)

    def finish(self, end_revision, data=None):
        self._diff.export()
        if data is None:
            data = self._diff.previous_metric_targets

        logging.info('Metric options: parsed up to revision %s', end_revision)
        super(Metric_Options_Collector, self).finish(end_revision, data=data)
