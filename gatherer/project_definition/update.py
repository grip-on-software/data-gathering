"""
Utilities for tracking updates between versions of a project definition.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import os
from typing import Any, Dict, Optional
from ..domain import Project, Source
from ..domain.sources import Sources
from ..version_control.repo import Version

class Update_Tracker:
    """
    Class that keeps track of the previous and current state of an incremental
    update, so that the data gatherer can resume from a previous known state.
    """

    def __init__(self, project: Project, source: Source,
                 target: str = 'metric_options') -> None:
        self._project = project
        self._source = source

        self._filename = project.export_key / f'{target}_update.json'

        self._file_loaded = False
        self._previous_data = None
        self._sources = Sources()
        self._versions: Dict[str, Version] = {}

    def get_start_revision(self, from_revision: Optional[Version] = None) -> Optional[Version]:
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

    def get_previous_data(self) -> Dict[str, Any]:
        """
        Retrieve the metadata retrieved from the latest unique revision that was
        parsed previously.
        """

        self._read()

        if self._previous_data is None:
            return {}

        return self._previous_data

    def _read(self) -> None:
        if self._file_loaded:
            return

        if self._filename.exists():
            with self._filename.open('r', encoding='utf-8') as update_file:
                data = json.load(update_file)

            self._previous_data = data['targets']
            if 'sources' in data:
                self._sources.load_sources(data['sources'])
                self._versions = data['versions']

        self._file_loaded = True

    def set_end(self, end_revision: Optional[Version],
                previous_data: Optional[Dict[str, Any]]) -> None:
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
            with open(self._filename, 'w', encoding='utf-8') as update_file:
                json.dump(data, update_file)
