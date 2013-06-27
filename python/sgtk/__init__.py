"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

ALT_API_NAME = "tank"
THIS_MODULE_NAME = "sgtk"

# first import our alternative API
import tank

# now go through and duplicate all entries in sys.modules 
import sys
for x in sys.modules.keys():
    
    if x.startswith("%s." % ALT_API_NAME):
        # this is a submodule inside the alternative API
        # create a copy in sys.modules with our own name
        new_name = "%s.%s" % (THIS_MODULE_NAME, x[len(ALT_API_NAME)+1:])
        sys.modules[new_name] = sys.modules[x]
    
    elif x == ALT_API_NAME:
        # this is the actual alternative module
        # remap that too - this means we are remapping ourselves...
        sys.modules[THIS_MODULE_NAME] = sys.modules[x]
        # now ensure that the other module has sys imported,
        # otherwise we can no longer access sys or any of the predefined variables
        # beyond this point. 
        ALT_API_NAME = "tank"
        THIS_MODULE_NAME = "sgtk"
        import sys

# lastly, remap the globals accessor to point at our new module
globals()[THIS_MODULE_NAME] = sys.modules[THIS_MODULE_NAME]


