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

    def __init__(self, parent):
        """
        Constructor.
        """
        QtGui.QDialog.__init__(self, parent)
        

def create_dialog(dialog_class):
    """
    Creates a dialog instance for a given dialog class
    """
    return dialog_class()