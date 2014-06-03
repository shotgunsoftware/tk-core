# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods for loading and managing plugins, e.g. Apps, Engines, Hooks etc.

"""

import os
import sys
import imp
import traceback

from .errors import TankError

def load_plugin(plugin_file, valid_base_class):
    """
    Load a plugin into memory and extract its single interface class. 
    """
    # construct a uuid and use this as the module name to ensure
    # that each import is unique
    import uuid
    module_uid = uuid.uuid4().hex 
    module = None
    try:
        imp.acquire_lock()
        module = imp.load_source(module_uid, plugin_file)
    except Exception:
        # dump out the callstack for this one -- to help people get good messages when there is a plugin error        
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        message = ""
        message += "Failed to load plugin %s. The following error was reported:\n" % plugin_file
        message += "Exception: %s - %s\n" % (exc_type, exc_value)
        message += "Traceback (most recent call last):\n"
        message += "\n".join( traceback.format_tb(exc_traceback))
        raise TankError(message)
    finally:
        imp.release_lock()
    
    # cool, now validate the module
    found_classes = list()
    introspection_error_reported = None
    try:
        for var in dir(module):
            value = getattr(module, var)
            if isinstance(value, type) and issubclass(value, valid_base_class) and value != valid_base_class:
                found_classes.append(value)
    except Exception, e:
        introspection_error_reported = str(e)

    if introspection_error_reported:
            raise TankError("Introspection error while trying to load and introspect file %s. "
                            "Error Reported: %s" % (plugin_file, e))

    elif len(found_classes) < 1:
        # missing class!
        msg = ("Error loading the file '%s'. Couldn't find a class deriving from the base class '%s'. "
               "You need to have exactly one class defined in the file deriving from that base class. "
               "If your file looks fine, it is possible that the cached .pyc file that python "
               "generates is invalid and this is causing the error. In that case, please delete "
               "the pyc file and try again." % (plugin_file, valid_base_class.__name__))
        
        raise TankError(msg)
        
    # when we do inheritance, the file effectively contains more than one class object
    # make sure we return the last class definition in the file, e.g. the actual
    # class and not the base class.
    return found_classes[-1]


