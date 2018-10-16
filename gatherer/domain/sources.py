"""
Collections of sources.
"""

from collections import MutableSet
import json
import os
from .source import Source

class Sources(MutableSet):
    """
    Collection of sources related to a project.
    """

    def __init__(self, sources_path=None, follow_host_change=True):
        # pylint: disable=super-init-not-called
        self._sources_path = sources_path
        self._follow_host_change = follow_host_change

        self.clear()

        if self._sources_path is not None:
            self.load_file(self._sources_path)

    def load_file(self, path):
        """
        Import a JSON file containing source dictionaries into the collection.
        """

        if os.path.exists(path):
            with open(path, 'r') as sources_file:
                sources = json.load(sources_file)
                self.load_sources(sources)

    def load_sources(self, sources_data):
        """
        Import a sequence of source dictionaries into the collection.
        """

        for source_data in sources_data:
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

    def include(self, source):
        """
        Add a new source to the collection.

        This source only becomes persistent if the sources are exported later on
        using `export`.
        """

        self._sources.add(source)
        self._source_urls[source.url] = source

        environment = source.environment
        if environment is None:
            return

        if environment not in self._source_environments:
            self._source_environments[environment] = set()

        self._source_environments[environment].add(source)

    def delete(self, source):
        """
        Remove an existing source from the project domain.

        This method raises a `KeyError` if the source cannot be found.

        The removal only becomes persistent if the sources are exported later on
        using `export`.
        """

        self._sources.remove(source)
        del self._source_urls[source.url]

        environment = source.environment
        if environment in self._source_environments:
            self._source_environments[environment].remove(source)
            if not self._source_environments[environment]:
                del self._source_environments[environment]

    def replace(self, source):
        """
        Replace an existing source with one that has the exact same URL as
        the one being replaced.

        This method raises a `KeyError` if the existing source cannot be found.

        The replacement only becomes persistent if the sources are exported
        later on using `export`.
        """

        existing_source = self._source_urls[source.url]
        self.remove(existing_source)
        self.add(source)

    def has_url(self, url):
        """
        Check whether there is a source with the exact same URL as the one that
        is provided.
        """

        return url in self._source_urls

    def __contains__(self, source):
        return source in self._sources

    def __iter__(self):
        return iter(self._sources)

    def __len__(self):
        return len(self._sources)

    def add(self, value):
        return self.include(value)

    def discard(self, value):
        try:
            self.delete(value)
        except KeyError:
            pass

    def remove(self, value):
        self.delete(value)

    def clear(self):
        self._sources = set()
        self._source_urls = {}
        self._source_environments = {}

    def get_environments(self):
        """
        Yield Source objects that are distinctive for each environment.

        The environments may contain multiple sources that share some traits,
        and can thus be used to find more sources within the environment.

        Only one source per environment is provided by the generator.
        """

        for sources in list(self._source_environments.values()):
            try:
                yield next(iter(sources))
            except StopIteration:
                return

    def find_source_type(self, source_type):
        """
        Retrieve the first found `Source` object for a specific source type.
        """

        return next(self.find_sources_by_type(source_type))

    def find_sources_by_type(self, source_type):
        """
        Provide a generator with `Source` objects for a specific source type.
        """

        for source in self._sources:
            if isinstance(source, source_type):
                yield source

    def export(self):
        """
        Export a list of dictionaries of the sources in the collection,
        such that they can be reestablished in another location or process.
        The list is returned, and if a sources path was provided in the
        constructor, then the JSON-encoded version is also exported to the file.
        """

        sources_data = []
        for source in self._sources:
            sources_data.append(source.export())

        if self._sources_path is not None:
            with open(self._sources_path, 'w') as sources_file:
                json.dump(sources_data, sources_file)

        return sources_data

    def export_environments(self, environments_path):
        """
        Export a description of each environment as a JSON list to the file
        located at `environments_path`.
        """

        environment_data = []
        for environment, sources in list(self._source_environments.items()):
            source = next(iter(sources))
            environment_data.append({
                "type": source.environment_type,
                "url": source.environment_url,
                "environment": environment,
                "version": source.version
            })
        with open(environments_path, 'w') as environments_file:
            json.dump(environment_data, environments_file)

    def __repr__(self):
        return 'Sources({!r})'.format(self._sources)
