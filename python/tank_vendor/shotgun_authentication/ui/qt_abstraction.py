# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Imports Qt without having to worry whether we are using PyQt4 or PySide.
"""
try:
    from PySide import QtCore, QtGui
except ImportError:
    try:
        from PyQt4 import QtCore, QtGui
    except:
        pass
