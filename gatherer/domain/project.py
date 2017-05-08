"""
Project domain object
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import object
import configparser
import json
import os
from .source import Source, GitLab

class Project_Meta(object):
    """
    Class that holds information that may span multiple projects.
    """

    _settings = None
    _project_definitions = None

    @classmethod
    def _init_settings(cls):
        cls._settings = configparser.RawConfigParser()
        cls._settings.read("settings.cfg")

    @property
    def settings(self):
        """
        Retrieve the parsed settings of the data gathering pipeline.
        """

        if self._settings is None:
            self._init_settings()

        return self._settings

    @classmethod
    def _init_project_definitions(cls):
        if cls._settings is None:
            cls._init_settings()

        source_type = cls._settings.get('definitions', 'source_type')
        name = cls._settings.get('definitions', 'name')
        url = cls._settings.get('definitions', 'url')
        cls._project_definitions = Source.from_type(source_type,
                                                    name=name, url=url)

    @property
    def project_definitions_source(self):
        """
        Retrieve a `Source` object that describes the project definitions
        version control system.
        """

        if self._project_definitions is None:
            self._init_project_definitions()

        return self._project_definitions

class Project(Project_Meta):
    """
    Object that holds information about a certain project.

    This includes configuration such JIRA keys, long names, descriptions,
    locations of source repositories, and so on.

    The data is read from multiple sources, namely settings and gathered data,
    which is available on a case-by-case basis. Only data that has been gathered
    can be accessed.
    """

    def __init__(self, project_key, follow_host_change=True,
                 export_directory='export'):
        super(Project, self).__init__()

        # JIRA project key
        self._project_key = project_key

        self._export_directory = export_directory
        self._follow_host_change = follow_host_change

        # Long project name used in repositories and quality dashboard project
        # definitions.
        self._project_name = self._get_setting('projects')
        self._main_project = self._get_setting('subprojects')

        self._sources = None
        self._sources_path = os.path.join(self.export_key, 'data_sources.json')
        self._load_sources()

    def _get_setting(self, group):
        if self.settings.has_option(group, self._project_key):
            return self.settings.get(group, self._project_key)
        else:
            return None

    def _load_sources(self):
        if self._sources is not None:
            return

        self._sources = set()
        if os.path.exists(self._sources_path):
            with open(self._sources_path, 'r') as sources_file:
                sources = json.load(sources_file)
                for source_data in sources:
                    source_type = source_data.pop('type')
                    source = Source.from_type(source_type,
                                              follow_host_change=self._follow_host_change,
                                              **source_data)
                    self.add_source(source)

    def add_source(self, source):
        """
        Add a new source to the project domain.

        This source only becomes persistent if the sources are exported later on
        using `export_sources`.
        """

        self._sources.add(source)

    def remove_source(self, source):
        """
        Remove an existing source from the project domain.

        This method raises a `KeyError` if the source cannot be found.

        The removal only becomes persistent if the sources are exported later on
        using `export_sources`.
        """

        self._sources.remove(source)

    def make_export_directory(self):
        """
        Ensure that the export directory exists, or create it if it is missing.
        """

        if not os.path.exists(self.export_key):
            os.makedirs(self.export_key)

    def export_sources(self):
        """
        Export data about all registered sources so that they can be
        reestablished in another process.
        """

        data = []
        for source in self._sources:
            data.append(source.export())

        self.make_export_directory()
        with open(self._sources_path, 'w') as sources_file:
            json.dump(data, sources_file)

    @property
    def sources(self):
        """
        Retrieve all sources of the project.
        """

        return self._sources

    @property
    def export_key(self):
        """
        Retrieve the directory path used for project data exports.
        """

        return os.path.join(self._export_directory, self._project_key)

    @property
    def dropins_key(self):
        """
        Retrieve the directory path where dropins for this project may be found.
        """

        return os.path.join('dropins', self._project_key)

    @property
    def key(self):
        """
        Retrieve the key that can be used for identifying data belonging
        to this project.
        """

        return self._project_key

    @property
    def jira_key(self):
        """
        Retrieve the key used for the JIRA project.
        """

        return self._project_key

    @property
    def gitlab_group_name(self):
        """
        Retrieve the name used for a GitLab group that contains all repositories
        for this project on some GitLab service.

        If there are no sources with GitLab tokens for this project, then this
        property returns `None`.
        """

        source = self.gitlab_source
        if source is None:
            return None
        if source.gitlab_group is not None:
            return source.gitlab_group

        return self._project_name

    @property
    def gitlab_source(self):
        """
        Retrieve a source providing credentials for a GitLab instance.

        If there is no such source, then this property returns `None`.
        """

        self._load_sources()
        for source in self._sources:
            if isinstance(source, GitLab):
                return source

        return None

    @property
    def quality_metrics_name(self):
        """
        Retrieve the name used in the quality metrics project definition.

        If the project has no long name or if it is a subproject of another
        project, then this property returns `None`.
        """

        if self._project_name is None or self._main_project is not None:
            return None

        return self._project_name

    @property
    def main_project(self):
        """
        Retrieve the main project for this subproject, or `None` if the project
        has no known hierarchical relation with another project.
        """

        return self._main_project
