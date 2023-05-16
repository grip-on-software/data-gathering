"""
Parse schemas containing guild topics and dates to a JSON file containing
guild information.

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
from typing import Any, Dict, List, Optional, Union
import xlrd
import yaml
from gatherer.log import Log_Setup
from gatherer.utils import format_date

class Schema:
    """
    Base schema object.
    """

    def __init__(self, config: Dict[str, Any], path: str) -> None:
        self._config = config
        self._path = path
        try:
            self._year = int(path.split('.')[0].split(' ')[-1])
        except ValueError:
            self._year = datetime.now().year

    @staticmethod
    def _validate_date(guild_date: Dict[str, Union[str, int, datetime]]) \
            -> Optional[datetime]:
        found_date = guild_date.get("date")
        if isinstance(found_date, datetime):
            return found_date

        if "weekday" in guild_date and "week" in guild_date:
            date = '{guild_date["weekday"]} {guild_data["week"]} {self._year}'
            return datetime.strptime(date, '%w %W %Y')

        return None

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        Add command-line arguments to the parser.
        """

        raise NotImplementedError('Must be implemented by subclasses')

    def parse(self) -> List[Dict[str, Any]]:
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

    def __init__(self, config: Dict[str, Any], path: str) -> None:
        super().__init__(config, path)
        self._workbook = xlrd.open_workbook(path)
        self._worksheet = self._workbook.sheet_by_index(0)
        self._placeholders: Dict[str, List[str]] = self._config['placeholders']

    def _find_types(self) -> Dict[int, str]:
        columns: Dict[str, str] = self._config['columns']
        types: Dict[int, str] = {}
        for col in range(self.SKIP_COLUMNS, self._worksheet.ncols):
            value = self._worksheet.cell_value(self.SKIP_ROWS, col)
            if value in columns:
                types[col] = columns[value]

        return types

    def _set_date(self, guild_date: Dict[str, Union[str, int, datetime]],
                  col_type: Dict[str, str], value: str) -> None:
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

    def _check_placeholder(self, col_type: str, value: str) -> Optional[str]:
        for placeholder in self._placeholders.get(col_type, []):
            if placeholder in value:
                value = ''

        if value == '' and col_type == 'topic':
            return None

        return value.strip()

    def _get_guild(self, row: int, types: Dict[int, str]) -> Optional[Dict[str, Any]]:
        guild_date: Dict[str, Union[str, int, datetime]] = {}
        guild: Dict[str, Any] = {}
        for col, col_type in types.items():
            value = self._worksheet.cell_value(row, col)

            if isinstance(col_type, dict):
                self._set_date(guild_date, col_type, value)
            else:
                placeholder_value = self._check_placeholder(col_type, value)
                if placeholder_value is None:
                    return None

                guild[col_type] = placeholder_value

        date = self._validate_date(guild_date)
        if date is None:
            return None

        guild["date"] = format_date(date)
        return guild

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('Excel', 'Excel parser')
        group.add_argument('--filename', help='Excel file name',
                           default='Guilds.xls')

    def parse(self) -> List[Dict[str, Any]]:
        guilds: List[Dict[str, Any]] = []

        types = self._find_types()
        for row in range(self.SKIP_ROWS + 1, self._worksheet.nrows):
            guild = self._get_guild(row, types)
            if guild is not None:
                guilds.append(guild)

        return guilds

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain guild dates from Excel and output JSON"
    parser = ArgumentParser(description=description)
    Excel_Schema.add_arguments(parser)

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    with open('guilds.yml', encoding='utf-8') as config_file:
        config = yaml.safe_load(config_file)

    schema = Excel_Schema(config, args.filename)
    guilds = schema.parse()
    with open('data_guilds.json', 'w', encoding='utf-8') as guilds_file:
        json.dump(guilds, guilds_file)

if __name__ == '__main__':
    main()
