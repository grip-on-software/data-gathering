"""
Parse XLS worksheets containing sheet counts per project/team, per month to
a JSON file containing sheet counts per project, per month.

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
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import xlrd
import yaml
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.table import Key_Table, Row
from gatherer.utils import format_date

Seats = Dict[datetime, float]
Teams = Dict[str, Seats]

def parse_filename(file_path: Path, config: Dict[str, Any]) \
        -> Optional[datetime]:
    """
    Retrieve the forecast date from the filename.
    """

    try:
        return datetime.strptime(str(file_path), str(config.get('filename')))
    except ValueError:
        logging.exception('Could not parse filename date format')
        return None

def gather_months(workbook: xlrd.book.Book, worksheet: xlrd.sheet.Sheet,
                  forecast_date: Optional[datetime]) -> List[datetime]:
    """
    Retrieve a list of valid month names from the column headers.

    This excludes the dates after the forecast date.
    """

    months: List[datetime] = []
    for col in range(1, worksheet.ncols):
        month = xlrd.xldate.xldate_as_datetime(worksheet.cell_value(0, col),
                                               workbook.datemode)
        if forecast_date is not None and month > forecast_date:
            return months

        months.append(month)

    return months

def validate_project_name(name: str, config: Dict[str, Any]) -> Optional[str]:
    """
    Check whether the given project name is applicable.

    Returns an altered project name, `None` if the name is not relevant or
    raises a `StopIteration` if no names can be found after this one.
    """

    if name == '':
        return None

    if any(name.startswith(ignore) for ignore in config['ignore']):
        raise StopIteration

    prefixes: List[str] = config['prefixes']
    for prefix in prefixes:
        if name.startswith(prefix):
            return name[len(prefix):]

    return name

def get_seats(worksheet: xlrd.sheet.Sheet, row: int, col: int) -> float:
    """
    Get the seat count from the worksheet at the coordinates and convert it
    to a float.
    """

    seats_value = worksheet.cell_value(row, col)

    try:
        seats = float(seats_value)
    except ValueError:
        if seats_value != '':
            logging.exception('Could not convert value in (%d,%d): %s',
                              row, col, seats_value)
        seats = 0.0

    return seats

def fill_teams(worksheet: xlrd.sheet.Sheet, months: Sequence[datetime],
               config: Dict[str, Any], teams: Teams) -> Teams:
    """
    Fill a dictionary of team names and dictionaries of months and seat
    counts from the worksheet.
    """

    for row in range(1, worksheet.nrows):
        try:
            name = validate_project_name(worksheet.cell_value(row, 0), config)
        except StopIteration:
            break

        if name is None:
            continue

        teams.setdefault(name, {})

        for index, month in enumerate(months):
            teams[name][month] = get_seats(worksheet, row, index + 1)

    return teams

def update_table(table: Key_Table, keys: Sequence[str], month_seats: Seats) -> None:
    """
    Update a `Key_Table` object with the months and seat counts that are
    applicable to the current project, which is one of the keys that the
    counts apply to.
    """

    for month, seats in list(month_seats.items()):
        row: Row = {
            'month': format_date(month, '%Y-%m'),
            'seats': str(seats / len(keys))
        }
        old_row = table.get_row(row)
        if old_row is not None:
            row['seats'] = str(float(row['seats']) + float(old_row['seats']))
            table.update(old_row, row)
        else:
            table.append(row)

def format_seats(config: Dict[str, Any], teams: Teams, project: Project) -> Key_Table:
    """
    Convert a dictionary of teams and monthly seat counts into a list of
    records containing months and weighted seat counts for the given project.
    """

    projects: Dict[str, Union[str, List[str]]] = config['projects']
    output = Key_Table('seats', 'month')
    for name, month_seats in list(teams.items()):
        if name in projects:
            project_key = projects[name]
            if isinstance(project_key, str):
                keys = [project_key]
            else:
                keys = project_key

            if project.jira_key in keys:
                update_table(output, keys, month_seats)
        else:
            logging.info('Unknown project %s', name)

    return output

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain seat counts from Excel and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument('project', help='JIRA project key')
    parser.add_argument('--filename', help='Excel file name(s) or pattern(s)',
                        nargs='+', default='Seats.xls')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    update_path = Path(project.export_key, 'seats_files.json')
    if update_path.exists():
        with update_path.open('r', encoding='utf-8') as update_file:
            filenames = json.load(update_file)
            if set(filenames) == set(args.filename):
                logging.info('Seat files were already read for %s, skipping.',
                             project.jira_key)
                return

    with open('seats.yml', encoding='utf-8') as config_file:
        config: Dict[str, Any] = yaml.safe_load(config_file)

    teams: Teams = {}
    for pattern in args.filename:
        logging.info('Expanding pattern %s', pattern)
        for file_path in Path('.').glob(pattern):
            logging.info('Parsing file %s', file_path)

            forecast_date = parse_filename(file_path, config)
            logging.info('Forecast date: %r', forecast_date)

            workbook = xlrd.open_workbook(str(file_path))
            worksheet = workbook.sheet_by_name(str(config.get('sheet')))

            months = gather_months(workbook, worksheet, forecast_date)

            teams = fill_teams(worksheet, months, config, teams)

    output = format_seats(config, teams, project)
    output.write(project.export_key)

    with open(update_path, 'w', encoding='utf-8') as update_file:
        json.dump(args.filename, update_file)

if __name__ == '__main__':
    main()
