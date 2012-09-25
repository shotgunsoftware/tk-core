"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------


"""

from tank import Hook
from tank import TankError

class SnapshotHistoryPostQuickdaily(Hook):
    
    def execute(self, mov_path, version_id, comments, **kwargs):
        app = self.parent
        # get app
        publish_app = app.engine.apps["tk-nuke-publish"]
        # try to snapshot the file and add a comment
        try:
            comment = "Automatically snapshotted after Quickdaily. "
            comment += "User Comments: %s " % comments
            comment += "Version id: %d " % version_id
            comment += "Quicktime: %s" % mov_path
            publish_app.snapshot(comment)
        except TankError:
            # fine, means file wasn't a proper snapshot
            pass
            