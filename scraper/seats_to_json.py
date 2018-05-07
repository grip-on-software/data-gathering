"""
Parse XLS worksheets containing sheet counts per project/team, per month to
a JSON file containing sheet counts per project, per month.
"""

import argparse
import datetime
import glob
import json
import logging
import os.path
import xlrd
import yaml
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.table import Key_Table
from gatherer.utils import format_date

def parse_filename(filename, config):
    """
    Retrieve the forecast date from the filename.
    """

    try:
        forecast_date = datetime.datetime.strptime(os.path.basename(filename),
                                                   config.get('filename'))
    except ValueError:
        logging.exception('Could not parse filename date format')
        return None

    return forecast_date

def gather_months(workbook, worksheet, forecast_date):
    """
    Retrieve a list of valid month names from the column headers.

    This excludes the dates after the forecast date.
    """

    months = []
    for col in range(1, worksheet.ncols):
        month = xlrd.xldate.xldate_as_datetime(worksheet.cell_value(0, col),
                                               workbook.datemode)
        if month > forecast_date:
            return months

        months.append(month)

    return months

def validate_project_name(name, config):
    """
    Check whether the given project name is applicable.

    Returns an altered project name, `False` if the name is not relevant or
    raises a `StopIteration` if no names can be found after this one.
    """

    if name == '':
        return False

    if any(name.startswith(ignore) for ignore in config.get('ignore')):
        raise StopIteration

    for prefix in config.get('prefixes'):
        if name.startswith(prefix):
            return name[len(prefix):]

    return name

def get_seats(worksheet, row, col):
    """
    Get the seat count from the worksheet at the coordinates and convert it
    to a float.
    """

    seats = worksheet.cell_value(row, col)

    try:
        seats = float(seats)
    except ValueError:
        if seats != '':
            logging.exception('Could not convert value in (%d,%d): %s',
                              row, col, seats)
        seats = 0.0

    return seats

def fill_teams(worksheet, months, config, teams):
    """
    Fill a dictionary of team names and dictionaries of months and seat
    counts from the worksheet.
    """

    for row in range(1, worksheet.nrows):
        try:
            name = validate_project_name(worksheet.cell_value(row, 0), config)
        except StopIteration:
            break

        if name is False:
            continue

        teams.setdefault(name, {})

        for index, month in enumerate(months):
            teams[name][month] = get_seats(worksheet, row, index + 1)

    return teams

def update_table(table, keys, month_seats):
    """
    Update a `Key_Table` object with the months and seat counts that are
    applicable to the current project, which is one of the keys that the
    counts apply to.
    """

    for month, seats in list(month_seats.items()):
        row = {
            'month': format_date(month, '%Y-%m'),
            'seats': seats / len(keys)
        }
        if table.has(row):
            old_row = table.get_row(row)
            row['seats'] += old_row['seats']
            table.update(old_row, row)
        else:
            table.append(row)

def format_seats(config, teams, project):
    """
    Convert a dictionary of teams and monthly seat counts into a list of
    records containing months and weighted seat counts for the given project.
    """

    projects = config.get('projects')
    output = Key_Table('seats', 'month')
    for name, month_seats in list(teams.items()):
        if name in projects:
            if isinstance(projects[name], list):
                keys = projects[name]
            else:
                keys = [projects[name]]

            if project.jira_key in keys:
                update_table(output, keys, month_seats)
        else:
            logging.info('Unknown project %s', name)

    return output

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain seat counts from Excel and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('project', help='JIRA project key')
    parser.add_argument('--filename', help='Excel file name(s) or pattern(s)',
                        nargs='+', default='Seats.xls')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)
    update_path = os.path.join(project.export_key, 'seats_files.json')
    if os.path.exists(update_path):
        with open(update_path) as update_file:
            filenames = json.load(update_file)
            if set(filenames) == set(args.filename):
                logging.info('Seat files were already read for %s, skipping.',
                             project.jira_key)
                return

    with open('seats.yml') as config_file:
        config = yaml.load(config_file)

    teams = {}
    for pattern in args.filename:
        logging.info('Expanding pattern %s', pattern)
        for filename in glob.glob(pattern):
            logging.info('Parsing file %s', filename)

            forecast_date = parse_filename(filename, config)
            logging.info('Forecast date: %r', forecast_date)

            workbook = xlrd.open_workbook(filename)
            worksheet = workbook.sheet_by_name(config.get('sheet'))

            months = gather_months(workbook, worksheet, forecast_date)

            teams = fill_teams(worksheet, months, config, teams)

    output = format_seats(config, teams, project)
    output.write(project.export_key)

    with open(update_path, 'w') as update_file:
        json.dump(args.filename, update_file)

if __name__ == '__main__':
    main()
