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
In rare cases, a core update may break or cause instability to apps and engines.
This is typically when an app has inadvertently been 'taking advantage' of a 
bug or where improvements in for example error handling which causes undesired 
side effects in apps. 

While these situations should be very rare, it is still worth tracking them in the core
so that we at least can give a heads up warning when we know that something is going
to cause future friction. 
"""

from ..deploy import util 

black_list = [ 
    
    # fix for the bug where context.as_template_fields return the wrong data for
    # context objects which have no corresponding objects on disk.
    {"system_name": "tk-multi-workfiles", 
     "version": "v0.3.15", 
     "message": "Version v0.3.15 (and older) of the Shotgun File Manager contains logic which may "
                "generate error messages when ran with future versions of the Core API. "
                "We strongly recommend you to upgrade to the latest version of the workfiles "
                "app as soon as you can." }

]

def compare_against_black_list(descriptor):
    """
    Looks at the current descriptor and checks it against the black list.
    A list of strings are returned, containing all relevant deprecation messages.
    """
    messages = []
    for x in black_list:
        if descriptor.get_system_name() == x["system_name"]:
            if util.is_version_newer( descriptor.get_version(), x["version"] ) == False:
                # this item matches the sytem name (e.g. tk-multi-foobar)
                # and its version is not more recent than the one in the black list!
                messages.append(x["message"])
    
    return messages
          