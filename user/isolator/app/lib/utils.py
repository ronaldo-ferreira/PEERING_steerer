"""
Utilities for supporting netconfig library.
"""
import sys


class AlwaysContainsSet(set):
    """A set that always returns that it contains a given key.

    Subclassed the set type to ensure that isinstance(inst, set) will still
    return true if a caller checks.
    """

    def __len__(self):
        return sys.maxint

    def __bool__(self):
        return True

    def __contains__(self, key):
        return True
