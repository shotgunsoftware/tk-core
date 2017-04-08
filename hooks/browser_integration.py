# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that provides utilities used by Toolkit's browser integration.
"""

import os
import hashlib
import json
import fnmatch
import datetime

import sgtk

class BrowserIntegration(sgtk.Hook):
    def process_commands(self, commands):
        """
        Allows for pre-processing of the commands that will be returned to the client.
        The default implementation here makes use of this to filter out any commands
        that were not registered by an app. This will remove standard commands that
        are not desirable for display in the SG web app, such as the
        "Reload and Restart" command.

        :param list commands: A list of dictionaries, each containing information
            about a command to be passed up to the client. Each dict will include
            the following keys: name, title, app_name, deny_permissions, and
            supports_multiple_selection.

        :returns: Processed commands.
        :rtype: list
        """
        # Filter out any commands that didn't come from an app. This will
        # filter out things like the "Reload and Restart" command.
        filtered = list()

        for command in commands:
            if command["app_name"] is not None:
                filtered.append(command)
            else:
                sgtk.platform.current_engine().logger.debug(
                    "Command filtered out for browser integration: %s" % command
                )
        return filtered



