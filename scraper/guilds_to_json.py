"""
Parse schemas containing guild topics and dates to a JSON file containing
guild information.
"""

import argparse
from datetime import datetime
import json
import xlrd
import yaml
from gatherer.log import Log_Setup
from gatherer.utils import format_date

class Schema(object):
    """
    Base schema object.
    """

    def __init__(self, config, path):
        self._config = config
        self._path = path
        try:
            self._year = int(path.split('.')[0].split(' ')[-1])
        except ValueError:
            self._year = datetime.now().year

    def _validate_date(self, guild_date):
        if "date" in guild_date:
            return guild_date["date"]

        if "weekday" in guild_date and "week" in guild_date:
            date = '{weekday} {week} {year}'.format(year=self._year, **guild_date)
            return datetime.strptime(date, '%w %W %Y')

        return None

    @classmethod
    def add_arguments(cls, parser):
        """
        Add command-line arguments to the parser.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def parse(self):
        """
        Parse the schema.
        """

        raise NotImplementedError("Must be implemented by subclasses")

class Excel_Schema(Schema):
    """
    Excel worksheet schema.
    """

    SKIP_ROWS = 2
    SKIP_COLUMNS = 1

    def __init__(self, config, path):
        super(Excel_Schema, self).__init__(config, path)
        self._workbook = xlrd.open_workbook(path)
        self._worksheet = self._workbook.sheet_by_index(0)
        self._placeholders = self._config.get('placeholders')

    def _find_types(self):
        columns = self._config.get('columns')
        types = {}
        for col in range(self.SKIP_COLUMNS, self._worksheet.ncols):
            value = self._worksheet.cell_value(self.SKIP_ROWS, col)
            if value in columns:
                types[col] = columns[value]

        return types

    def _set_date(self, guild_date, col_type, value):
        if "value" in col_type and value != '':
            guild_date[col_type["type"]] = col_type["value"]
        if col_type["type"] == "week":
            try:
                guild_date["week"] = int(value)
            except ValueError:
                pass
        else:
            try:
                guild_date["date"] = xlrd.xldate.xldate_as_datetime(value, self._workbook.datemode)
            except ValueError:
                pass

    def _check_placeholder(self, col_type, value):
        for placeholder in self._placeholders.get(col_type, []):
            if placeholder in value:
                value = ''

        if value == '' and col_type == 'topic':
            return None

        return value.strip()

    def _get_guild(self, row, types):
        guild_date = {}
        guild = {}
        for col, col_type in types.items():
            value = self._worksheet.cell_value(row, col)

            if isinstance(col_type, dict):
                self._set_date(guild_date, col_type, value)
            else:
                value = self._check_placeholder(col_type, value)
                if value is None:
                    return None

                guild[col_type] = value

        date = self._validate_date(guild_date)
        if date is None:
            return None

        guild["date"] = format_date(date)
        return guild

    @classmethod
    def add_arguments(cls, parser):
        group = parser.add_argument_group('Excel', 'Excel parser')
        group.add_argument('--filename', help='Excel file name',
                           default='Guilds.xls')

    def parse(self):
        guilds = []

        types = self._find_types()
        for row in range(self.SKIP_ROWS + 1, self._worksheet.nrows):
            guild = self._get_guild(row, types)
            if guild is not None:
                guilds.append(guild)

        return guilds

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain guild dates from Excel and output JSON"
    parser = argparse.ArgumentParser(description=description)
    Excel_Schema.add_arguments(parser)

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    with open('guilds.yml') as config_file:
        config = yaml.load(config_file)

    schema = Excel_Schema(config, args.filename)
    guilds = schema.parse()
    with open("data_guilds.json", "w") as guilds_file:
        json.dump(guilds, guilds_file)

if __name__ == '__main__':
    main()
