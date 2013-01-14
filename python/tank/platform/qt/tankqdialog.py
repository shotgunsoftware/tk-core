"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Default implementation for the Tank Dialog

"""

from . import QtCore, QtGui

class TankQDialog(QtGui.QDialog):
    """
    The default implementation used is essentially just a passthrough to QDialog.
    """

    def __init__(self):
        """
        Constructor.
        """
        # by default, parent windows to the currently active window
        parent = QtGui.QApplication.activeWindow()
        QtGui.QDialog.__init__(self, parent)
        

