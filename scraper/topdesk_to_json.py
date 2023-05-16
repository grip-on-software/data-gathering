"""
Script to convert a Topdesk dump CSV file to JSON.

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

from argparse import ArgumentParser, Namespace
import csv
import json
import logging
from typing import Dict, List, Optional, Pattern, TextIO, Tuple, \
    TYPE_CHECKING
import regex
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.utils import get_local_datetime, format_date, parse_unicode
if TYPE_CHECKING:
    # pylint: disable=import-error
    from _typeshed import SupportsRichComparison

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Parse a Topdesk data dump and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--file", default='topdesk-reservations.csv',
                        help="File name of dump to read")
    parser.add_argument("--whitelist-only", default=False, action='store_true',
                        dest="whitelist_only",
                        help="Only include whitelisted reservations")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

class Topdesk_Parser:
    """
    Topdesk CSV dump reader and reservations exporter.
    """

    PROJECT_ALL = 'all'

    _first_name = r'\p{Lu}(?:\p{Ll}+|\.)'
    _last_name = r'\p{Lu}\p{Ll}{2,}'
    _affix = r'van(?: t| de| den| der)?|de'
    _full_name = rf'{_first_name}(?: (?:{_affix}))? {_last_name}(?: {_last_name})?'
    _name = rf'^{_full_name}(?: \(\p{{Lu}}[^)]+\)| - \p{{Lu}}[\w-]+| en {_full_name})?$'
    _name_regex = regex.compile(_name, flags=regex.UNICODE)

    def __init__(self, project: Project) -> None:
        self._project = project
        self._project_key = project.key

        self._config = Configuration.get_config('topdesk')

        self._project_pass: Optional[str] = None
        if self._config.has_option('projects', self._project_key):
            self._project_pass = self._config.get('projects', self._project_key)

        self._names = [
            (key, name.encode('utf-8').decode('unicode_escape'))
            for (key, name) in self._config.items('names')
        ]
        whitelist = [
            (project_key.upper(), regex.compile(search, flags=regex.IGNORECASE))
            for project_key, search in self._config.items('whitelist')
        ]
        self._whitelist = list(sorted(whitelist, key=self._sort_whitelist))
        blacklist = self._config.get('blacklist', 'all')
        self._blacklist = regex.compile(blacklist, flags=regex.IGNORECASE)

    def _sort_whitelist(self, pair: Tuple[str, Pattern[str]]) \
            -> 'SupportsRichComparison':
        if pair[0] == self.PROJECT_ALL.upper():
            # Sort last
            return (True,)

        if pair[0] == self._project_key:
            # Sort first
            return -1

        # Sort normally
        return pair[0]

    @staticmethod
    def parse_date(date: str) -> str:
        """
        Parse a date and time from the Topdesk data.
        """

        local_date = get_local_datetime(date, date_format='%Y-%m-%d %H:%M')
        return format_date(local_date)

    def get_reservations(self, input_file: TextIO,
                         whitelist_only: bool = False) -> List[Dict[str, str]]:
        """
        Retrieve all relevant reservations belonging to the project from
        the input file, excluding the reservations that are blacklisted or
        belong to a different project.
        """

        reservations: List[Dict[str, str]] = []
        if self._project_pass is None and \
            all(self._project_key != key for key, whitelist in self._whitelist):
            return reservations

        reader = csv.DictReader(input_file)
        for line in reader:
            reservation = self._parse_reservation(line, whitelist_only)
            if reservation is not None:
                reservations.append(reservation)

        return reservations

    def _check_whitelist(self, fields: Dict[str, str]) -> bool:
        whitelisted = False
        for project_key, whitelist in self._whitelist:
            if whitelist.search(fields['description']):
                logging.debug('Whitelisted as %s: %s', project_key,
                              fields['description'])
                whitelisted = True
                if project_key != self.PROJECT_ALL.upper():
                    fields['project'] = project_key
                    break

        return whitelisted

    def _parse_reservation(self, line: Dict[str, str], whitelist_only: bool) \
            -> Optional[Dict[str, str]]:
        fields = {key: line[name] for key, name in self._names}
        if self._blacklist.search(fields['description']):
            logging.debug('Blacklisted: %s', fields['description'])
            return None
        if all(part in fields['description'] \
                for part in fields['requester'].split()):
            return None

        if self._project_pass == fields['project_pass']:
            fields['project'] = self._project_key

        whitelisted = self._check_whitelist(fields)
        if not whitelisted:
            if whitelist_only:
                logging.debug('Not whitelisted: %s', fields['description'])
                return None

            unicode_description = parse_unicode(fields['description'])
            if self._name_regex.match(unicode_description):
                logging.debug('Name: %s', fields['description'])
                return None

        if 'project' in fields and fields['project'] == self._project_key:
            return {
                'reservation_id': fields['reservation_id'],
                'requester': fields['requester'],
                'number_of_people': fields['number_of_people'],
                'description': fields['description'],
                'start_date': self.parse_date(fields['start_date']),
                'end_date': self.parse_date(fields['end_date']),
                'prepare_date': self.parse_date(fields['prepare_date']),
                'close_date': self.parse_date(fields['close_date'])
            }

        return None

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project_key = str(args.project)
    project = Project(project_key)
    parser = Topdesk_Parser(project)

    with open(args.file, 'r', encoding='utf-8') as input_file:
        reservations = parser.get_reservations(input_file, args.whitelist_only)

    logging.info('Project %s: %d reservations', project_key, len(reservations))

    export_path = project.export_key / 'data_reservations.json'
    with export_path.open('w', encoding='utf-8') as export_file:
        json.dump(reservations, export_file, indent=4)

if __name__ == "__main__":
    main()
