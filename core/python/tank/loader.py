"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

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
    # TODO: when we version up the interface need to take this into account here
    found_classes = list()
    error_reported = None
    try:
        for var in dir(module):
            value = getattr(module, var)
            if isinstance(value, type) and issubclass(value, valid_base_class) and value != valid_base_class:
                found_classes.append(value)
    except Exception, e:
        error_reported = str(e)
    
    if len(found_classes) < 1:
        if error_reported:
            raise TankError("Trying to find %s class in %s generated the "
                            "following error: %s" % (str(valid_base_class), plugin_file, e))
        else:
            raise TankError("Could not find %s class in %s!" % (str(valid_base_class), plugin_file))
        
    elif len(found_classes) > 1:
        raise TankError("Found more than one %s class in %s!" % (str(valid_base_class), plugin_file))
    
    return found_classes[0]


