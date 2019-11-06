from __future__ import absolute_import

from tank_vendor.shotgun_api3.lib import six

# Import constants and functions that won't be wrapped
from re import (DEBUG, I, IGNORECASE, L, LOCALE, # noqa import into namespace
                M, MULTILINE, S, DOTALL, U, UNICODE, X, VERBOSE)
from re import escape # noqa import into namespace

# In Python 3, regular expression metacharacters match unicode characters where in
# Python 2 they hadn't.  To reproduce the previous behavior, Python 3 introduces a
# new re.ASCII flag, which does not exist in Python 2.  For Python 2, we can leave
# the re behavior as-is.
if six.PY2:
    from re import compile, findall, match, search, split, sub

# For Python 3, we'll wrap the re functions to inject the ASCII flag when necessary
# to maintain the previous behavior.
else:
    import re as _re

    def _re_wrap(fn, flags_arg_position):
        def wrapper(*args, **kwargs):
            if len(args) > flags_arg_position:
                # If flags is provided positionally, and the UNICODE flag
                # is not present, add the ASCII flag
                if not args[flags_arg_position] & _re.UNICODE:
                    args = list(args)
                    args[flags_arg_position] |= _re.ASCII
            elif 'flags' in kwargs and not kwargs['flags'] & _re.UNICODE:
                # If flags is provided as a kwarg, and the UNICODE flag
                # is not present, add the ASCII flag
                kwargs['flags'] |= _re.ASCII
            else:
                # If no flags were specified, add a flags kwarg with the ASCII
                # flag.
                kwargs['flags'] = _re.ASCII
            return fn(*args, **kwargs)
        return wrapper

    # Since the flags arg is sometimes provided positionally, we'll specify the
    # argument's position to our wrapper so it can handle this.  These interfaces
    # all remained unchanged between Python 2 and 3, so positionally providing
    # flags does not break.
    compile = _re_wrap(_re.compile, 1)
    findall = _re_wrap(_re.findall, 2)
    match = _re_wrap(_re.match, 2)
    search = _re_wrap(_re.search, 2)
    split = _re_wrap(_re.split, 3)
    sub = _re_wrap(_re.sub, 4)
