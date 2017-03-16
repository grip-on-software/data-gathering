"""
Script to convert a Topdesk dump CSV file to JSON.
"""

import argparse
import ConfigParser
import csv
import json
import os
import re
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Parse a Topdesk data dump and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--file", default='topdesk-reservations.csv',
                        help="File name of dump to read")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

class Topdesk_Parser(object):
    """
    Topdesk CSV dump reader and reservations exporter.
    """

    def __init__(self, project):
        self._project = project
        self._project_key = project.key

        self._config = ConfigParser.RawConfigParser()
        self._config.read('topdesk.cfg')
        self._project_pass = self._config.get('projects', self._project_key)
        self._names = [
            (key, name.decode('string-escape'))
            for (key, name) in self._config.items('names')
        ]
        self._whitelist = [
            (project_key, re.compile(search, flags=re.IGNORECASE))
            for project_key, search in self._config.items('whitelist')
        ]
        blacklist = self._config.get('blacklist', 'all')
        self._blacklist = re.compile(blacklist, flags=re.IGNORECASE)

    @staticmethod
    def parse_date(date):
        """
        Parse a date and time from the Topdesk data.
        """

        return date

    def get_reservations(self, input_file):
        """
        Retrieve all relevant reservations belonging to the project from
        the input file, excluding the reservations that are blacklisted or
        belong to a different project.
        """

        reservations = []
        reader = csv.DictReader(input_file)
        for line in reader:
            reservation = self._parse_reservation(line)
            if reservation is not None:
                reservations.append(reservation)

        return reservations

    def _parse_reservation(self, line):
        fields = dict([(key, line[name]) for key, name in self._names])
        if self._blacklist.match(fields['description']):
            return None
        if all(part in fields['description'] \
                for part in fields['requester'].split()):
            return None

        if self._project_pass == fields['project_pass']:
            fields['project'] = self._project_key

        for project_key, search in self._whitelist:
            if search.match(fields['description']):
                if project_key != 'all':
                    fields['project'] = project_key

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

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    project = Project(project_key)
    parser = Topdesk_Parser(project)

    with open(args.file) as input_file:
        reservations = parser.get_reservations(input_file)

    export_filename = os.path.join(project.export_key, 'data_reservations.json')
    with open(export_filename, 'w') as export_file:
        json.dump(reservations, export_file, indent=4)

if __name__ == "__main__":
    main()
