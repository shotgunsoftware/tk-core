import sys
import os
import logging

import six
if six.PY3:
    from httplib2 import Http, ProxyInfo, socks
    from ssl import SSLError as SSLHandshakeError
else:
    from .lib.httplib2 import Http, ProxyInfo, socks, SSLHandshakeError

from .lib.sgtimezone import SgTimezone
if six.PY3:
    from xmlrpc.client import Error, ProtocolError, ResponseError
else:
    from .lib.xmlrpclib import Error, ProtocolError, ResponseError


LOG = logging.getLogger("shotgun_api3")
LOG.setLevel(logging.WARN)

try:
    import simplejson as json
except ImportError:
    LOG.debug("simplejson not found, dropping back to json")
    try:
        import json as json
    except ImportError:
        LOG.debug("json not found, dropping back to embedded simplejson")
        # We need to munge the path so that the absolute imports in simplejson will work.
        dir_path = os.path.dirname(__file__)
        lib_path = os.path.join(dir_path, 'lib')
        sys.path.append(lib_path)
        from .lib import simplejson as json
        sys.path.pop()


import mimetypes    # used for attachment upload
try:
    mimetypes.add_type('video/webm','.webm') # try adding to test for unicode error
except (UnicodeDecodeError, TypeError):
    # Ticket #25579: python bug on windows with unicode
    # Ticket #23371: mimetypes initialization fails on Windows because of TypeError 
    #               (http://bugs.python.org/issue23371)
    # Use patched version of mimetypes
    from .lib import mimetypes as mimetypes
