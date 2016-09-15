# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .event_engine import EngineEvent

class FileCloseEvent(EngineEvent):
    """
    An object representation of a file-open event.
    """
    def __init__(self):
        """
        Constructor.

        :param str file_path: The path to the file opened.
        """
        super(FileCloseEvent, self).__init__()
