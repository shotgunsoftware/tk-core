"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

# this class contains QT adapters and functionality for application agnostic QT usage.
# at engine initialization, the variables QtCore and QtGui are created by the engine
# init method and set to appropriate libraries.

# in apps and frameworks, for an agnostic qt access, you can then go:

# from tank.platform.qt import QtCore, QtGui

# in addition to this, the engine will add a class called TankQDialog which represents
# a QDialog object potentially subclassed by an engine. Use this class when you want to 
# create dialog windows.