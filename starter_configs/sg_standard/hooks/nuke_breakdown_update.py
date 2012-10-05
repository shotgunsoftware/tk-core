"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that contains the logic for updating a reference from one version to another.
Coupled with the scene scanner hook - for each type of reference that the scanner
hook can detect, a piece of upgrade logic should be provided in this file.

"""

import nuke

from tank import Hook

class MayaBreakdownUpdate(Hook):

    def execute(self, items, **kwargs):

        # items is a list of dicts. Each dict has items node_type, node_name and path

        for i in items:
            node_name = i["node_name"]
            node_type = i["node_type"]
            new_path = i["path"]

            engine = self.parent.engine
            engine.log_debug("%s: Updating to version %s" % (node_name, new_path))

            if node_type == "Read":
                node = nuke.toNode(node_name)
                node.knob("file").setValue(new_path)
            else:
                raise Exception("Unknown node type %s" % node_type)

