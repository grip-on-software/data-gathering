# Stubs for hqlib.domain.software_development.environment (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..measurement.measurable import MeasurableObject
from .requirement import Requirement, RequirementSubject
from typing import Sequence, Type

class Environment(RequirementSubject, MeasurableObject):
    default_name: str = ...
    default_short_name: str = ...
    @staticmethod
    def default_requirements() -> Sequence[Type[Requirement]]: ...
    @staticmethod
    def optional_requirements() -> Sequence[Type[Requirement]]: ...
