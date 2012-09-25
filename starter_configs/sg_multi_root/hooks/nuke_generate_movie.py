"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Quicktime generator Hook that is called from the Nuke publisher.
This hook will call out to the tk-nuke-makequicktime hook and use this
to generate quicktimes.

"""

from tank import Hook
import os

class GenerateQuicktime(Hook):
    
    def execute(self, source_path, targets, **kwargs):
        # use the default quicktime creation app
        engine = self.parent.engine
        app = engine.apps["tk-nuke-makequicktime"]
        
        # ensure things are reset
        app.reset()
        
        status = {}
        try:
            # set source data
            app.set_up_input(source_path)
            
            # now set up a quicktime for each profile
    
            # also prepare our return value back to the publisher
            # for every target, return a dictionary of values that
            # we use to extend the version record that is created
            for (profile_name, mov_path) in targets.items():
                
                # note! This is also a good time to look at the platform
                # in case you may want to generate things differently
                # on for example a mac and a pc.
                app.add_quicktime_output(profile_name, mov_path)
                
                first_frame = app.get_first_frame()
                last_frame = app.get_last_frame()
                
                # return a dictionary with custom fields to be populated
                d = {}
                d["sg_first_frame"] = first_frame
                d["sg_last_frame"] = last_frame
                d["frame_count"] = (last_frame - first_frame) + 1
                d["frame_range"] = "%d-%d" % (first_frame, last_frame)
                d["sg_frames_have_slate"] = True
                d["sg_movie_has_slate"] = True
                
                status[profile_name] = d
            
            # and finally do it!
            app.render()    
        
        except Exception, e:
            engine.log_exception("Could not execute quicktime creator!")
        finally:
            app.reset()
        
        return status
        
