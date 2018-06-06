"""
Module that increases compatibility with earlier project definitions by
augmenting the hqlib module with replacement domain objects.
"""

from builtins import object
import mock
from hqlib import domain

# Define some classes that are backward compatible with earlier versions of
# hqlib (quality_report, qualitylib). This suppresses argument exceptions.
class Compatibility(object):
    """
    Handler for classes that are backward compatible with earlier versions
    of those classes in distributed modules.
    """

    replacements = {}

    @classmethod
    def replaces(cls, target):
        """
        Decorator method for a class that replaces another class `target`.
        """

        def decorator(subject):
            """
            Decorator that registers the class `subject` as a replacement.
            """

            cls.replacements[target] = subject
            return subject

        return decorator

    @classmethod
    def get_replacement(cls, name, member):
        """
        Find a suitable replacement for a class whose interface should be
        mostly adhered, but its functionality should not be executed.
        """

        if member in cls.replacements:
            return cls.replacements[member]

        replacement = mock.Mock(name=name, spec_set=member)

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

@Compatibility.replaces(domain.TechnicalDebtTarget)
class TechnicalDebtTarget(domain.TechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    def __init__(self, target_value, explanation='', unit=''):
        super(TechnicalDebtTarget, self).__init__(target_value, explanation)

@Compatibility.replaces(domain.DynamicTechnicalDebtTarget)
class DynamicTechnicalDebtTarget(domain.DynamicTechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    # pylint: disable=too-many-arguments
    def __init__(self, initial_target_value, initial_datetime,
                 end_target_value, end_datetime, explanation='', unit=''):
        parent = super(DynamicTechnicalDebtTarget, self)
        parent.__init__(initial_target_value, initial_datetime,
                        end_target_value, end_datetime, explanation)

def produce_mock(name):
    """
    Method which produces a dynamic class, which in turn produces a magic
    mock object upon instantiation. The dynamic class is given the name.

    This can be used to pass isinstance checks against this class.
    """

    def __new__(cls, *args, **kwargs):
        obj = mock.MagicMock(spec=cls)
        obj.name = cls.__name__
        obj(*args, **kwargs)
        return obj

    return type(name, (object,), {"__new__": __new__})

COMPACT_HISTORY = produce_mock('CompactHistory')
