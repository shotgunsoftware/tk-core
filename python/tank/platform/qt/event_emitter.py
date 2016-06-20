# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import QtCore

class EventEmitter(QtCore.QObject):
    """
    A container object for event signals.

    :signal event(object): A generic event signal housing a Python object.
        Typically this object will be an :class:`sgtk.platform.EngineEvent`
        object.
    """
    event = QtCore.Signal(object)
