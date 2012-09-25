"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Example pre-publish validation hook which checks that the scene contains a single transform node

"""

from tank import Hook
import maya.cmds as cmds

class ValidateSceneDag(Hook):
    
    def execute(self, **kwargs):
        if not cmds.objExists("|ROOT"):
            # scene must contain a node called ROOT!
            msg = ("Scene does not contain a top level node named ROOT!\n"
                  "This is required for the pipeline to be able to process this asset.\n\n"
                  "[Please note that this is an example validation hook and can be \n"
                  "turned off or reconfigured easily!]")            
            raise Exception(msg)
