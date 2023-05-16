"""
Abstract base classes that other objects inherit.

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

from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional, Tuple, Union, TYPE_CHECKING
from jira import Issue
if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from . import Jira, FieldValue
else:
    Jira = object
    FieldValue = object

TableKey = Optional[Union[str, Tuple[str, ...]]]

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
    Abstract base class with the minimal required interface from Jira fields.
    """

    def __init__(self, jira: Jira, name: str, **data: FieldValue) -> None:
        self.jira = jira
        self.name = name
        self.data = data

    def parse(self, issue: Any) -> Optional[str]:
        """
        Retrieve the field from the issue and parse it. Parsing can include
        type casting using field parsers, or it may perform more intricate
        steps with larger resources within the issue.

        This method either returns the parsed value, indicating that it is
        a piece of data related to this issue version, or `None`, indicating
        that the data was stored or handled elsewhere.
        """

        raise NotImplementedError("Must be implemented by subclass")

    @property
    def search_field(self) -> Optional[str]:
        """
        JIRA field name to be added to the search query, or `None` if this
        field is always available within the result.
        """

        raise NotImplementedError("Subclasses must extend this property")

class Base_Changelog_Field(Base_Jira_Field):
    """
    Abstract base class with the minimum required interface for parsing
    changelog fields from Jira API responses.
    """

    def parse_changelog(self, entry: Any, diffs: Dict[str, Optional[str]],
                        issue: Issue) -> Optional[str]:
        """
        Parse changelog information from a changelog entry.

        The `entry` may be some resource, such as a main changelog entry or
        specific change item from the changelog entry payload. The caller
        supplies what it believes the changelog parser can handle best.
        The `diffs` argument is a reference to the current difference dictionary
        for inspection by the changelog field or its type cast parsers.
        Finally, `issue` is the issue resource.

        The returned value is an appropriate (preferably string) format of
        the value in this field before the change, or a custom value that
        should be handled later on. `None` indicates that the value was handled
        elsewhere.
        """

        raise NotImplementedError("Must be implemented by subclasses")
