"""
Project domain object
"""

import ConfigParser
import json
import os
from .source import Source, GitLab

class Project(object):
    """
    Object that holds information about a certain project.

    This includes configuration such JIRA keys, long names, descriptions,
    locations of source repositories, and so on.

    The data is read from multiple sources, namely settings and gathered data,
    which is available on a case-by-case basis. Only data that has been gathered
    can be accessed.
    """

    _settings = None

    def __init__(self, project_key, follow_host_change=True):
        if self._settings is None:
            self._settings = ConfigParser.RawConfigParser()
            self._settings.read("settings.cfg")

        # JIRA project key
        self._project_key = project_key
        self._follow_host_change = follow_host_change

        # Long project name used in repositories and quality dashboard project
        # definitions.
        if self._settings.has_option('projects', self._project_key):
            self._project_name = self._settings.get('projects',
                                                    self._project_key)
        else:
            self._project_name = None

        if self._settings.has_option('subprojects', self._project_key):
            self._main_project = self._settings.get('subprojects',
                                                    self._project_key)
        else:
            self._main_project = None

        self._sources = None
        self._sources_path = os.path.join(self.export_key, 'data_sources.json')
        self._load_sources()

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

    def export_sources(self):
        """
        Export data about all registered sources so that they can be
        reestablished in another process.
        """

        data = []
        for source in self._sources:
            data.append(source.export())

        if not os.path.exists(self.export_key):
            os.mkdir(self.export_key)

        with open(self._sources_path, 'w') as sources_file:
            json.dump(data, sources_file)

    @property
    def export_key(self):
        """
        Retrieve the key used for project data exports.
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

        if self.gitlab_source is None:
            return None

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
