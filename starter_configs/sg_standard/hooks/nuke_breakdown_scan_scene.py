"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that scans the scene for referenced maya files. Used by the breakdown to
establish a list of things in the scene.

This implementation supports the following types of references:

* maya references
* texture file input nodes

"""

import os

import nuke

from tank import Hook

class ScanScene(Hook):

    def execute(self, **kwargs):
        reads = []

        # first let's look at maya references
        for node in nuke.allNodes("Read"):
            node_name = node.name()

            # note! We are getting the "abstract path", so contains
            # %04d and %V rather than actual values.
            path = node.knob('file').value().replace("/", os.path.sep)

            reads.append( {"node": node_name, "type": "Read", "path": path})

        return reads
