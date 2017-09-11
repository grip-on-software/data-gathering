"""
Module for collecting data from various versions of project definitions.
"""

from builtins import object
import logging
import os.path
from .metric import Metric_Difference
from .parser import Metric_Options_Parser, Project_Parser, Sources_Parser
from .update import Update_Tracker
from ..domain import Source
from ..domain.source.types import Source_Type_Error

class Collector(object):
    """
    Class that collects and aggregates data from different versions of project
    definition files.
    """

    FILENAME = 'project_definition.py'

    def __init__(self, project, repo_path=None, target='project_definition',
                 **options):
        if repo_path is None:
            repo_path = project.get_key_setting('definitions', 'path',
                                                project.quality_metrics_name)

        self._project = project
        self._update_tracker = Update_Tracker(self._project, target=target)
        repo_class = project.project_definitions_source.repository_class
        self._repo = repo_class(project.project_definitions_source,
                                repo_path, project=self._project)

        if project.quality_metrics_name not in repo_path:
            self._filename = '{}/{}'.format(project.quality_metrics_name,
                                            self.FILENAME)
        else:
            self._filename = self.FILENAME

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
                                           descending=False, stats=False)
        end_revision = None
        for index, version in enumerate(versions):
            logging.debug('Collecting version %s (%d in sequence)',
                          version['version_id'], index)
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
            parser.load_definition(self._filename, contents)
            result = parser.parse()
            self.aggregate_result(version, result)
        except RuntimeError as error:
            logging.warning("Problem with revision %s: %s",
                            version['version_id'], str(error))

    def collect_latest(self):
        """
        Collect information from the latest version of the project definition,
        and finalize the collection immediately.
        """

        latest_version = self._repo.get_latest_version()
        self.collect_version({"version_id": latest_version})
        self.finish(latest_version)

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

class Project_Collector(Collector):
    """
    Collector that retrieves project information.
    """

    def __init__(self, project, **kwargs):
        super(Project_Collector, self).__init__(project,
                                                target='project_meta',
                                                **kwargs)
        self._meta = {}

    def build_parser(self, version):
        return Project_Parser(**self._options)

    def aggregate_result(self, version, result):
        self._meta = result

    @property
    def meta(self):
        """
        Retrieve the parsed project metadata.
        """

        return self._meta

class Sources_Collector(Collector):
    """
    Collector that retrieves version control sources from project definitions.
    """

    SOURCES_MAP = {
        'Subversion': 'subversion',
        'Git': 'git',
        'History': 'history',
        'CompactHistory': 'compact-history'
    }

    def __init__(self, project, **kwargs):
        super(Sources_Collector, self).__init__(project,
                                                target='project_sources',
                                                **kwargs)

        repo_path = self._repo.repo_directory
        if project.quality_metrics_name in repo_path:
            self._repo_path = os.path.dirname(os.path.abspath(repo_path))
        else:
            self._repo_path = repo_path

    def build_parser(self, version):
        return Sources_Parser(self._repo_path, **self._options)

    def _build_metric_source(self, name, metric_source, metric_type, source_type):
        try:
            source = Source.from_type(source_type, name=name,
                                      url=metric_source[metric_type])

            if not self._project.has_source(source):
                self._project.sources.add(source)
        except Source_Type_Error:
            logging.exception('Could not register source')

    def aggregate_result(self, version, result):
        for name, metric_source in result.items():
            for metric_type, source_type in self.SOURCES_MAP.items():
                # Loop over all known metric source class names and convert
                # them to our own Source objects.
                if metric_type in metric_source:
                    self._build_metric_source(name, metric_source,
                                              metric_type, source_type)

class Metric_Options_Collector(Collector):
    """
    Collector that retrieves changes to metric targets from project definitions.
    """

    def __init__(self, project, **kwargs):
        super(Metric_Options_Collector, self).__init__(project,
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
        if end_revision is None:
            logging.info('Metric options: No new revisions to parse')
        else:
            logging.info('Metric options: parsed up to revision %s',
                         end_revision)

        self._diff.export()
        if data is None:
            data = self._diff.previous_metric_targets

        super(Metric_Options_Collector, self).finish(end_revision, data=data)
