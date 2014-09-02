# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import QtCore, QtGui
from .ui_progress_dialog import Ui_ProgressDialog


class ProgressDialog(QtGui.QWidget):
    """
    Not found UI dialog.
    """
    
    def __init__(self):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)
        
        # now load in the UI that was created in the UI designer
        self.ui = Ui_ProgressDialog() 
        self.ui.setupUi(self)
        
        
    def set_contents(self, title, details):
        self.ui.title.setText(title)
        self.ui.details.setText(details)
                
                
                
    @property
    def hide_tk_title_bar(self):
        """
        Tell the system to not show the std toolbar
        """
        return True
        
