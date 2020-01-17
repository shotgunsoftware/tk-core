from ..shotgun_api3.lib import six

# import the proper implementation into the module namespace depending on the
# current python version.  PyYAML supports python 2/3 by forking the code rather
# than with a single cross-compatible module. Rather than modify third party code,
# we'll just import the appropriate branch here.
if six.PY3:
    from .python3 import *
else:
    from .python2 import *
