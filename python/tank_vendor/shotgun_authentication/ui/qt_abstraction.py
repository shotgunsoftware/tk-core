# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Cheat a bit here. When this module gets loaded, let's try to get the Qt from
# Toolkit in case it is available.
try:
    from PySide import QtCore, QtGui
except ImportError:
        from PyQt4 import QtCore, QtGui
