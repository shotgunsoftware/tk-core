"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

from tank import Hook
import shutil
import os
import nuke

class GetWriteNodes(Hook):
    
    def execute(self, templates_to_look_for, **kwargs):
        # 
        # get a bunch of write nodes in the scene
        # these need to be actual sequences on disk
        # 
        resolved_nodes = []
        
        # scan scene and add all tank nodes to list
        for node in nuke.allNodes("Write"):
            path = node.knobs()["file"].value()
            # see if this path matches any template
            norm_path = path.replace("/", os.path.sep)
            # test the templates
            for t in templates_to_look_for:
                if t.validate(norm_path): 
                    # yay - a matching path!
                    d = {}
                    d["template"] = t
                    d["fields"] = t.get_fields(norm_path)
                    d["node"] = node
                    resolved_nodes.append(d)
                    
            
        for node in nuke.allNodes("WriteTank"):
            try:
                path = node.knobs()["cached_path"].value()
            except:
                # fail gracefully - old version of tank write node?
                pass
            else:
                # see if this path matches any template
                norm_path = path.replace("/", os.path.sep)
                
                # test the templates
                for t in templates_to_look_for:
                    if t.validate(norm_path):
                        # yay - a matching path!
                        d = {}
                        d["template"] = t
                        d["fields"] = t.get_fields(norm_path)
                        d["node"] = node
                        resolved_nodes.append(d)

        return resolved_nodes
        
