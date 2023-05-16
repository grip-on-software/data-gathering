"""
Module that increases compatibility with earlier project definitions by
augmenting the hqlib module with replacement domain objects.

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

from typing import Any, Callable, Dict, Type, Union
from unittest.mock import Mock, MagicMock
from hqlib.domain import DomainObject, TechnicalDebtTarget, \
    DynamicTechnicalDebtTarget
from hqlib.typing import DateTime, MetricValue

DomainType = Type[Union[DomainObject, TechnicalDebtTarget]]

# Define some classes that are backward compatible with earlier versions of
# hqlib (quality_report, qualitylib). This suppresses argument exceptions.
class Compatibility:
    """
    Handler for classes that are backward compatible with earlier versions
    of those classes in distributed modules.
    """

    replacements: Dict[DomainType, DomainType] = {}

    @classmethod
    def replaces(cls, target: DomainType) -> Callable[[DomainType], DomainType]:
        """
        Decorator method for a class that replaces another class `target`.
        """

        def decorator(subject: DomainType) -> DomainType:
            """
            Decorator that registers the class `subject` as a replacement.
            """

            cls.replacements[target] = subject
            return subject

        return decorator

    @classmethod
    def get_replacement(cls, name: str, member: DomainType) -> DomainType:
        """
        Find a suitable replacement for a class whose interface should be
        mostly adhered, but its functionality should not be executed.
        """

        if member in cls.replacements:
            return cls.replacements[member]

        replacement = Mock(name=name, spec_set=member)

        configuration = {
            'name': name,
            'default_requirements.return_value': set(),
            'optional_requirements.return_value': set()
        }
        try:
            replacement.configure_mock(**configuration)
        except AttributeError:
            pass

        return replacement

@Compatibility.replaces(TechnicalDebtTarget)
class TechnicalDebtTargetCompat(TechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    def __init__(self, target_value: MetricValue, explanation: str = '',
                 **kwargs: str) -> None:
        super().__init__(target_value, explanation)

@Compatibility.replaces(DynamicTechnicalDebtTarget)
class DynamicTechnicalDebtTargetCompat(DynamicTechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    def __init__(self, initial_target_value: MetricValue,
                 initial_datetime: DateTime, end_target_value: MetricValue,
                 end_datetime: DateTime, explanation: str = '',
                 **kwargs: str) -> None:
        super().__init__(initial_target_value, initial_datetime,
                         end_target_value, end_datetime, explanation)

def produce_mock(name: str) -> Type[DomainObject]:
    """
    Method which produces a dynamic class, which in turn produces a magic
    mock object upon instantiation. The dynamic class is given the name.

    This can be used to pass isinstance checks against this class.
    """

    def __new__(cls: Type[DomainObject], *args: Any, **kwargs: Any) -> DomainObject:
        obj = MagicMock(spec=cls)
        obj.name = cls.__name__
        obj(*args, **kwargs)
        return obj

    return type(name, (DomainObject,), {"__new__": __new__})

# Produce mock source objects for classes that did not exist in earlier
# versions, which perform operations upon construction or which were metric
# source classes in earlier versions.
COMPACT_HISTORY = produce_mock('CompactHistory')
JIRA = produce_mock('Jira')
JIRA_FILTER = produce_mock('JiraFilter')
SONAR = produce_mock('Sonar')
