"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Default implementation for generating quicktimes. The default implementation uses RVIO
for quicktime generation but you can replace this with anything you like, ffmpeg or even
Nuke (this hook is always executed inside nuke).

"""

import os
import re
import time
import datetime
import subprocess
import platform

import nuke
import nukescripts

import tank
from tank import Hook

##################################################################################################
# in order for rvio to execute, the paths are defined here. These paths need to be customized
# for each setup. On windows, for simplicity, we recommend that rvio.exe is in the PATH.
#
#
#
RVIO_LINUX = "rvio"
RVIO_WINDOWS = "rvio.exe"
RVIO_MACOSX = "/Applications/RV64.app/Contents/MacOS/rvio"
#
#
##################################################################################################


class NukeReviewCreateContent(Hook):
    

    def execute(self,
                progress_callback,
                seq_template,
                mov_template,
                fields,
                filmstrip_thumb,
                thumbnail,
                shotgun_version_name,
                **kwargs):

        ########################################################################
        # setup

        self.seq_template = seq_template
        self.filmstrip_thumb = filmstrip_thumb
        self.thumbnail = thumbnail
        self.fields = fields

        # quicktime
        quicktime_path = mov_template.apply_fields(fields)

        # figure out sequence path. Choose right eye if stereo
        sequence_path = seq_template.apply_fields(fields)

        # make sure quicktime location exists
        mov_dir = os.path.dirname(quicktime_path)
        if not os.path.exists(mov_dir):
            os.makedirs(mov_dir, 0777)

        ########################################################################
        # generate quicktime using RVIO

        # now assemble command line
        cmd_line = list()
        cmd_line.append(self._get_rvio_executable())
        cmd_line.append("%s -o %s" % (sequence_path, quicktime_path))
        cmd_line.append("-v")

        # now add slate
        slate_data = self._make_slate_metadata(shotgun_version_name)
        md_str = " ".join(['"%s"="%s"' % (k, v) for (k, v) in slate_data.items()])
        cmd_line.append("""-leader simpleslate " " %s """ % md_str)
        # and a burnin frame counter 0.4 opacity font size 20
        cmd_line.append("-overlay frameburn 0.4 1.0 60.0")

        # now execute!
        full_cmd_line = " ".join(cmd_line)
        self._execute_rvio(full_cmd_line, progress_callback)

        ########################################################################
        # generate filmstrip thumbs using Nuke

        # this need to run in the main thread to interact with nuke.
        nuke.executeInMainThreadWithResult(self._generate_thumbnails)



    def _generate_thumbnails(self):
        """
        Generates a filmstrip and a normal thumbnail using Nuke
        """
        
        nodes = []
        frame_path = self.seq_template.apply_fields(self.fields)
        frame_paths = sorted(self.parent.tank.paths_from_template(self.seq_template, self.fields, skip_keys=["SEQ"]))

        if len(frame_paths) > 0:
            nukescripts.clear_selection_recursive()
            read = nuke.createNode("Read")
            nodes.append(read)
            read.knob("file").setValue(frame_path.replace(os.path.sep, "/")) # always /-style path
            first_frame = int(self.seq_template.get_fields(frame_paths[0]).get("SEQ", 1))
            last_frame = int(self.seq_template.get_fields(frame_paths[-1]).get("SEQ", len(frame_paths)))
            read.knob("first").setValue(first_frame)
            read.knob("last").setValue(last_frame)
            nukescripts.clear_selection_recursive()
            read.setSelected(True)

            # reformat all frames to 240px in width
            reformat = nuke.createNode("Reformat")
            nodes.append(reformat)
            reformat.knob("type").setValue("to box")
            reformat.knob("box_width").setValue(240)
            nukescripts.clear_selection_recursive()
            reformat.setSelected(True)

            filmstrip_last_frame = min(last_frame, 30)

            # retime the frames from min to max to 1 to 30(or max)
            retime = nuke.createNode("Retime")
            nodes.append(retime)
            retime.knob("input.first_lock").setValue(True)
            retime.knob("input.first").setValue(first_frame)
            retime.knob("input.last_lock").setValue(True)
            retime.knob("input.last").setValue(last_frame)
            retime.knob("output.first_lock").setValue(True)
            retime.knob("output.first").setValue(1)
            retime.knob("output.last_lock").setValue(True)
            retime.knob("output.last").setValue(filmstrip_last_frame)
            nukescripts.clear_selection_recursive()
            retime.setSelected(True)

            # contact sheet 1 row with 30(or max) columns
            sheet = nuke.createNode("ContactSheet")
            nodes.append(sheet)
            sheet.knob("width").setValue(240 * filmstrip_last_frame)
            sheet.knob("height").setValue(reformat.height())
            sheet.knob("rows").setValue(1)
            sheet.knob("columns").setValue(filmstrip_last_frame)
            sheet.knob("splitinputs").setValue(True)
            sheet.knob("startframe").setValue(1)
            sheet.knob("endframe").setValue(filmstrip_last_frame)
            nukescripts.clear_selection_recursive()
            sheet.setSelected(True)

            filmstrip_write = nuke.createNode("Write")
            nodes.append(filmstrip_write)
            filmstrip_write.knob("file").setValue(self.filmstrip_thumb.replace(os.path.sep, "/")) 
            nukescripts.clear_selection_recursive()

            thumbnail_write = nuke.createNode("Write")
            thumbnail_write.setInput(0, reformat)
            nodes.append(thumbnail_write)
            thumbnail_write.knob("file").setValue(self.thumbnail.replace(os.path.sep, "/")) 
            nukescripts.clear_selection_recursive()

            # figure out what view to use.
            nuke_views = nuke.views()
            if len(nuke_views) > 1 and "right" in nuke_views:
                views = ["right"]
            else:
                views = nuke_views

            # generate filmstrip
            nuke.execute(filmstrip_write, 1, 1, 1, views=views)

            # generate thumbnail
            middle_frame = len(frame_paths) / 2
            nuke.execute(thumbnail_write, middle_frame, middle_frame, 1, views=views)

            # cleanup
            for node in nodes:
                nuke.delete(node)


    def _make_slate_metadata(self, sg_version_name):
        """
        Builds a dictionary of name value pairs suitable for a slate page
        """
        
        metadata = {}

        metadata["Name"] = sg_version_name

        metadata[self.parent.context.entity["type"]] = self.parent.context.entity["name"]

        if self.parent.context.task:
            metadata["Task"] = self.parent.context.task["name"]

        elif self.parent.context.step:
            metadata["Step"] = self.parent.context.step["name"]

        metadata["Project"] = self.parent.context.project["name"]

        today = datetime.date.today()
        date_formatted = today.strftime("%d %b %Y")
        metadata["Date"] = date_formatted

        current_sg_user = tank.util.get_shotgun_user(self.parent.tank.shotgun)
        if current_sg_user:
            metadata["User"] = current_sg_user["name"]
        
        return metadata


    def _execute_rvio(self, cmd, progress_callback):
        """
        executes RVIO and connects its progress reporting to the tank progress reporter
        """
        full_stdout = list()
        proc = subprocess.Popen(cmd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        while True:
            try:
                line = proc.stdout.readline()
                if line == "":
                    break
                # get rid of \n whitespace at end
                line = line.rstrip()
                full_stdout.append(line)

                m = re.match("^INFO: writing frame [0-9]+ \(([0-9.]+)% done\)", line)
                if m is not None:
                    percent_progress = int(float(m.groups()[0]))
                    progress_callback(percent_progress)
            except Exception, e:
                # trap stuff like EINTR failures and other well known problems.
                time.sleep(0.2)

        # check return code
        proc.wait()
        if proc.returncode != 0:
            raise Exception("RVIO process returned error code %d: %s" % (proc.returncode,
                                                                         "\n".join(full_stdout)))

    def _get_rvio_executable(self):
        """
        Returns the appropriate rvio executable for the current platform
        """
        system = platform.system()

        if system == "Linux":
            return RVIO_LINUX
        elif system == "Darwin":
            return RVIO_MACOSX
        elif system == "Windows":
            return RVIO_WINDOWS
        else:
            raise Exception("Unknown platform %s!" % system)
        

