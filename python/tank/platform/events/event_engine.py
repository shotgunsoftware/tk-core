# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

class EngineEvent(object):
    """
    The base class of all concrete engine event objects. It provides a very
    basic interface that is expanded on in deriving classes.
    """
    _EVENT_TYPE = None

    def __init__(self):
        """
        Constructor.
        """
        self._event_type = self._EVENT_TYPE

    @property
    def event_type(self):
        """
        The string name of the event's type.
        """
        return self._event_type

    def __str__(self):
        return str(self.event_type)

