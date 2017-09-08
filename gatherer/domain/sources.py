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
        self._source_urls.add(source.url)

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
        self._source_urls.remove(source.url)

        environment = source.environment
        if environment in self._source_environments:
            self._source_environments[environment].remove(source)

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
        self._source_urls = set()
        self._source_environments = {}

    def get_environments(self):
        """
        Yield Source objects that are distinctive for each environment.

        The environments may contain multiple sources that share some traits,
        and can thus be used to find more sources within the environment.

        Only one source per environment is provided by the generator.
        """

        for sources in list(self._source_environments.values()):
            yield next(iter(sources))

    def find_source_type(self, source_type):
        """
        Retrieve a `Source` object for a specific source type.
        """

        for source in self._sources:
            if isinstance(source, source_type):
                return source

        return None

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

    def __repr__(self):
        return 'Sources({!r})'.format(self._sources)
