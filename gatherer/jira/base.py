"""
Abstract base classes that other objects inherit.

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

from abc import ABCMeta, abstractmethod
from typing import Dict, Optional, Tuple, Union, TYPE_CHECKING
from jira import Issue
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira, FieldValue
    from .changelog import ChangeHistory, ChangeItem
else:
    Jira = object
    FieldValue = object
    ChangeHistory = object
    ChangeItem = object

TableKey = Optional[Union[str, Tuple[str, ...]]]

class TableKeyError(Exception):
    """
    Error when requesting a table key.
    """

class Table_Source(metaclass=ABCMeta):
    """
    Abstract mixin class that indicates that subclasses might provide
    registration data for use in a `Table` instance.
    """

    @property
    @abstractmethod
    def table_key(self) -> TableKey:
        """
        Key to use for assigning unique rows to a table with parsed values of
        this type, or `None` if there are no keys in the table for this type.

        If this type is not meant to be used in a key at all, then accessing
        this property raises a `TableKeyError`.

        Note that actual registration of the table is dependent on other data
        sources, and thus the key may be different than this property.
        """

        return None

    @property
    @abstractmethod
    def table_name(self) -> Optional[str]:
        """
        Name to be used for the table where rows can be assigned to.

        Note that actual registration of the table is dependent on other data
        sources, and thus the table name may be different than this property.
        If the property returns `None`, then this indicates that this source
        does not have a need for a table with a certain name.
        """

        return None

class Base_Jira_Field(Table_Source):
    """
    Abstract base class with the minimum required interface for Jira fields
    from various sources in order to make them obtainable during issue searches.
    """

    def __init__(self, jira: Jira, name: str, **data: FieldValue) -> None:
        self.jira = jira
        self.name = name
        self.data = data

    @property
    def search_field(self) -> Optional[str]:
        """
        JIRA field name to be added to the search query, or `None` if this
        field is always available within the result.
        """

        raise NotImplementedError("Subclasses must extend this property")

class Base_Issue_Field(Base_Jira_Field):
    """
    Abstract base class with the minimum required interface for Jira fields from
    the current issue version.
    """

    def parse(self, issue: Issue) -> Optional[str]:
        """
        Retrieve the field from the issue and parse it. Parsing can include
        type casting using field parsers, or it may perform more intricate
        steps with larger resources within the issue.

        This method either returns the parsed value, indicating that it is
        a piece of data related to the current version of the issue, or `None`,
        indicating that the data was stored or handled elsewhere.
        """

        raise NotImplementedError("Must be implemented by subclass")

class Base_Changelog_Field(Base_Jira_Field):
    """
    Abstract base class with the minimum required interface for parsing
    changelog fields from Jira API responses.
    """

    def parse_changelog(self, entry: ChangeHistory,
                        diffs: Dict[str, Optional[str]],
                        issue: Issue,
                        item: Optional[ChangeItem]) -> Optional[str]:
        """
        Parse changelog information from a changelog entry.

        The `entry` is the main changelog history entry. The `diffs` argument
        is a reference to the current difference dictionary for inspection by
        the changelog field or its type cast parsers. `issue` is the issue
        resource from which the changelog entry is extracted. Finally, `item`
        is a change item with difference fields as values, or `None` if the
        field is registered to parse primary fields only.

        The returned value is an appropriate format of the value in this field
        before the change, or a custom value that should be handled later on.
        `None` indicates that the value was handled elsewhere or not available.
        """

        raise NotImplementedError("Must be implemented by subclasses")
