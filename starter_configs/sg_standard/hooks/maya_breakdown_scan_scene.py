"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that scans the scene for referenced maya files. Used by the breakdown to 
establish a list of things in the scene.

This implementation supports the following types of references:

* maya references
* texture file input nodes

"""

from tank import Hook
import maya.cmds as cmds
import pymel.core as pm
import os

class ScanScene(Hook):
    
    def execute(self, **kwargs):
        # scan scene for references.
        # for each reference found, return
        # a dict with keys node, type and path
        
        refs = []
        
        # first let's look at maya references        
        for x in pm.listReferences():
            node_name = x.refNode.longName()
            
            # get the path and make it platform dependent
            # (maya uses C:/style/paths)
            maya_path = x.path.replace("/", os.path.sep)
            
            refs.append( {"node": node_name, "type": "reference", "path": maya_path}) 
            
        # now look at file texture nodes
        for file_node in cmds.ls(l=True, type="file"):
            # ensure this is actually part of this scene and not referenced
            if cmds.referenceQuery(file_node, isNodeReferenced=True):
                # this is embedded in another reference, so don't include it in the
                # breakdown
                continue

            # get path and make it platform dependent
            # (maya uses C:/style/paths)
            path = cmds.getAttr("%s.fileTextureName" % file_node).replace("/", os.path.sep)
            
            refs.append( {"node": file_node, "type": "file", "path": path})
         
        print refs   
        return refs

    