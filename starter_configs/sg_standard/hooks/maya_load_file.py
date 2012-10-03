"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that loads items into the current scene. 

"""

from tank import Hook
import maya.cmds as cmds
import pymel.core as pm
import os

class MayaLoadFile(Hook):
    
    def execute(self, file_path, shotgun_data, **kwargs):
        
        pm.system.createReference(file_path)
        
        
    