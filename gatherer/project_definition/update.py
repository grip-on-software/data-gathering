"""
Module for tracking updates between versions of a project definition.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2024 Leon Helwerda

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
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, cast
from .base import MetricTargets, Revision
from ..domain import Project, Source
from ..domain.sources import Sources

Revisions = Dict[str, Revision]
SourceData = Dict[str, str]
SourceList = List[SourceData]
UpdateTrackerData = Dict[str, Union[SourceList, Revisions, MetricTargets]]

class Update_Tracker:
    """
    Class that keeps track of the previous and current state of an incremental
    update, so that the data gatherer can resume from a previous known state.
    """

    def __init__(self, project: Project, source: Source,
                 target: str = 'metric_options') -> None:
        self._project = project
        self._source = source

        self._filename = Path(project.export_key, f'{target}_update.json')

        self._file_loaded = False
        self._previous_data: Optional[MetricTargets] = None
        # Sources and versions per source URL to be added to the tracker
        self._sources = Sources()
        self._versions: Revisions = {}

    def get_start_revision(self, from_revision: Optional[Revision] = None) \
            -> Optional[Revision]:
        """
        Retrieve the revision at which to start collecting new versions.

        By default, this is the last revision that was parsed previously from
        this specific source, but this can be overridden using `from_revision`.
        """

        if from_revision is not None:
            return from_revision

        self._read()

        return self._versions.get(self._source.plain_url)

    def get_previous_data(self) -> MetricTargets:
        """
        Retrieve the metadata collected from the latest unique revision that was
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
                data: UpdateTrackerData = json.load(update_file)

            self._previous_data = cast(Optional[MetricTargets],
                                       data.get('targets'))
            self._sources.load_sources(cast(SourceList, data['sources']))
            self._versions = cast(Revisions, data.get('versions', {}))

        self._file_loaded = True

    def set_end(self, end_revision: Optional[Revision],
                previous_data: Optional[MetricTargets]) -> None:
        """
        Store the new current state of the data collection from the project
        definitions at the source. `end_revision` is the latest revision
        that was parsed in this run, or `None` if no revisions were parsed.
        `previous_data` is a serializable object to compare against for checking
        if the next update has changes.
        """

        self._project.sources.add(self._source)
        self._sources.add(self._source)

        if end_revision is None:
            # Mark as up to date to this time.
            os.utime(self._filename, None)
        else:
            self._read()

            self._versions[self._source.plain_url] = end_revision

            data: UpdateTrackerData = {
                'sources': self._sources.export(),
                'versions': self._versions
            }
            if previous_data is not None:
                data['targets'] = previous_data

            self._project.make_export_directory()
            try:
                with self._filename.open('w', encoding='utf-8') as update_file:
                    json.dump(data, update_file)
            except FileNotFoundError:
                logging.exception('Could not write update tracker for %s',
                                  self._project.key)
