"""
Abstract base classes that other objects inherit.
"""

from abc import ABCMeta, abstractproperty

class Table_Key_Source(object):
    # pylint: disable=too-few-public-methods

    """
    Abstract mixin class that indicates that subclasses might provide a key for
    use in a `Table` instance.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def table_key(self):
        """
        Key to use for assigning unique rows to a table with parsed values of
        this type, or `None` if there are no keyed tables for this type.
        """

        return None
