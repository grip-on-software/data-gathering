"""
Project domain object
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

from builtins import object
import json
import os
from ..config import Configuration
from .source import Source
from .source.github import GitHub
from .source.gitlab import GitLab

class Sources(object):
    """
    Collection of sources related to a project.
    """

    def __init__(self, sources_path, follow_host_change=True):
        self._sources_path = sources_path
        self._follow_host_change = follow_host_change

        self._sources = set()
        self._source_urls = set()
        self._source_environments = {}

        self._load_sources()

    def _load_sources(self):
        if os.path.exists(self._sources_path):
            with open(self._sources_path, 'r') as sources_file:
                sources = json.load(sources_file)
                for source_data in sources:
                    source_type = source_data.pop('type')
                    source = Source.from_type(source_type,
                                              follow_host_change=self._follow_host_change,
                                              **source_data)
                    self.add(source)

    def get(self):
        """
        Retrieve all sources in the collection.
        """

        return self._sources

    def add(self, source):
        """
        Add a new source to the collection.

        This source only becomes persistent if the sources are exported later on
        using `export`.
        """

        self._sources.add(source)
        self._source_urls.add(source.url)

        environment = source.environment
        if environment not in self._source_environments:
            self._source_environments[environment] = set()

        self._source_environments[environment].add(source)

    def remove(self, source):
        """
        Remove an existing source from the project domain.

        This method raises a `KeyError` if the source cannot be found.

        The removal only becomes persistent if the sources are exported later on
        using `export`.
        """

        self._sources.remove(source)
        self._source_urls.remove(source.url)
        self._source_environments[source.environment].remove(source)

    def has_url(self, url):
        """
        Check whether there is a source with the exact same URL as the one that
        is provided.
        """

        return url in self._source_urls

    def get_environments(self):
        """
        Yield Source objects that are distinctive for each environment.
        """

        for sources in list(self._source_environments.values()):
            yield next(iter(sources))

    def export(self):
        """
        Export data about all registered sources so that they can be
        reestablished in another process.
        """

        data = []
        for source in self._sources:
            data.append(source.export())

        with open(self._sources_path, 'w') as sources_file:
            json.dump(data, sources_file)

class Project_Meta(object):
    """
    Class that holds information that may span multiple projects.
    """

    _settings = None

    def __init__(self, export_directory='export', update_directory='update'):
        self._export_directory = export_directory
        self._update_directory = update_directory

    @classmethod
    def _init_settings(cls):
        cls._settings = Configuration.get_settings()

    def get_key_setting(self, section, key, *format_values, **format_args):
        """
        Retrieve a setting from a configuration section `section`. The `key`
        is used as the setting key.

        If additional arguments are provided, then the returned value has its
        placeholders ('{}' and the like) replaced with these positional
        arguments and keyword arguments.
        """

        value = self.settings.get(section, key)

        if format_values or format_args:
            value = value.format(*format_values, **format_args)

        return value

    @property
    def settings(self):
        """
        Retrieve the parsed settings of the data gathering pipeline.
        """

        if self._settings is None:
            self._init_settings()

        return self._settings

    @property
    def export_directory(self):
        """
        Retrieve the export directory.
        """

        return self._export_directory

    @property
    def update_directory(self):
        """
        Retrieve the remote update tracker directory.
        """

        return self._update_directory

    def make_project_definitions(self, base=False, project_name=None):
        """
        Create a `Source` object for a repository containing project definitions
        and metrics history, or other dependency files. If `base` is `True`,
        then the base code source repository is provided. If `project_name` is
        not `None`, then this is used for the quality metrics repository name.
        At least one of the two arguments must be provided, otherwise this
        method raises a `ValueError`.
        """

        if base:
            repo_name = self.get_key_setting('definitions', 'base')
            key = 'base_url'
        elif project_name is not None:
            repo_name = project_name
            key = 'url'
        else:
            raise ValueError('One of base or project_name must be non-falsy')

        source_type = self.get_key_setting('definitions', 'source_type')
        name = self.get_key_setting('definitions', 'name')
        url = self.get_key_setting('definitions', key, repo_name,
                                   project=not base)
        return Source.from_type(source_type, name=name, url=url)

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
                 export_directory='export', update_directory='update'):
        super(Project, self).__init__(export_directory, update_directory)

        # JIRA project key
        self._project_key = project_key

        # Long project name used in repositories and quality dashboard project
        # definitions.
        self._project_name = self.get_group_setting('projects')
        self._main_project = self.get_group_setting('subprojects')
        self._github_team = self.get_group_setting('teams')

        self._project_definitions = None

        sources_path = os.path.join(self.export_key, 'data_sources.json')
        self._sources = Sources(sources_path,
                                follow_host_change=follow_host_change)

    def get_group_setting(self, group):
        """
        Retrieve a setting from a configuration section `group`, using the
        project key as setting key. If the setting for this project does not
        exist, then `None` is returned.
        """

        if self.settings.has_option(group, self._project_key):
            return self.settings.get(group, self._project_key)

        return None

    def get_key_setting(self, section, key, *format_values, **format_args):
        """
        Retrieve a setting from a configuration section `section`, using the
        `key` as well as the project key, unless `project` is set to `False`.
        If a setting with a combined key that equals to the `key`, a period and
        the project key exists, then this setting's value is used, otherwise the
        `key` itself is used as the setting key.

        If additional arguments are provided, then the returned value has its
        placeholders ('{}' and the like) replaced with these positional
        arguments and keyword arguments.
        """

        project_key = '{}.{}'.format(key, self.key)
        project = format_args.pop('project', True)
        if project and self.settings.has_option(section, project_key):
            key = project_key

        return super(Project, self).get_key_setting(section, key,
                                                    *format_values,
                                                    **format_args)

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

    def has_source(self, source):
        """
        Check whether the project already has a source with the exact same URL
        as the provided `source`.
        """

        return self._sources.has_url(source.url)

    def get_environment_sources(self):
        """
        Yield a distinctive `Source` object for each known source environment.

        The environments may contain multiple sources that share some traits,
        and can thus be used to find more sources within the environment.
        """

        return self._sources.get_environments()

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

        self.make_export_directory()
        self._sources.export()

    @property
    def sources(self):
        """
        Retrieve all sources of the project.
        """

        return self._sources.get()

    @property
    def export_key(self):
        """
        Retrieve the directory path used for project data exports.
        """

        return os.path.join(self.export_directory, self._project_key)

    @property
    def update_key(self):
        """
        Retrieve the remote directory path used for obtaining update trackers
        from a synchronization server.
        """

        return os.path.join(self.update_directory, self._project_key)

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
    def github_team(self):
        """
        Retrieve the slug of the GitHub team that manages the repositories for
        this project.

        If there are no GitHub sources for this project or no defined team,
        then this property returns `None`.
        """

        source = self._find_source_type(GitHub)
        if source is None:
            return None

        return self._github_team

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

        return self._find_source_type(GitLab)

    def _find_source_type(self, source_type):
        for source in self.sources:
            if isinstance(source, source_type):
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

    @property
    def project_definitions_source(self):
        """
        Retrieve a `Source` object that describes the project definitions
        version control system. If the project has no definitions, then `None`
        is returned.
        """

        if self.quality_metrics_name is None:
            return None

        if self._project_definitions is None:
            project = self.quality_metrics_name
            self._project_definitions = \
                self.make_project_definitions(project_name=project)

        return self._project_definitions
