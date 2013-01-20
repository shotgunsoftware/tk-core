"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Default implementation for the Tank Dialog

"""

from . import QtCore, QtGui
from . import ui_tank_dialog
from . import TankDialogBase

TANK_TOOLBAR_HEIGHT = 45

class TankQDialog(TankDialogBase):
    """
    Wraps around app widgets. Contains Tank specific toolbars and configuration info
    in addition to the user object that it is hosting.
    """

    def __init__(self, title, bundle, widget, parent):
        """
        Constructor
        """
        TankDialogBase.__init__(self, parent)
        
        # set up the UI
        self.ui = ui_tank_dialog.Ui_TankDialog() 
        self.ui.setupUi(self)
        self.ui.label.setText(title)
        self.setWindowTitle(title)
        
        # parent the widget we are hosting into the dialog area
        widget.setParent(self.ui.page)
        self.ui.target.insertWidget(0, widget)
        # keep track of the widget
        self._widget = widget
        
        # adjust size of the outer window to match the hosted widget size
        self.resize(widget.width(), widget.height() + TANK_TOOLBAR_HEIGHT)
        
        # intercept the close event of the child widget
        # so that when the close event is emitted from the hosted widget,
        # we make sure to clo
        widget.closeEvent = lambda event: self._handle_child_close(event)
        
    def _handle_child_close(self, event):
        """
        Callback from the hosted widget's closeEvent.
        Make sure that when a close() is issued for the hosted widget,
        the parent widget is closed too.
        """
        # ACK the event to tell QT to proceed with the close 
        event.accept()
        
        # use accepted as the default exit code
        exit_code = QtGui.QDialog.Accepted    
        # look if the hosted widget has an exit_code we should pick up
        if hasattr(self._widget, "exit_code"):
            exit_code = self._widget.exit_code
        
        # close QDialog
        self.done(exit_code)
        
#    def on_arrow(self):
#        
#        self.ui.stackedWidget.setCurrentIndex(1)
        
#        self.ui.page_2.show()
#        self.ui.page_2.raise_()                     
#        
#        anim = QtCore.QPropertyAnimation(self.ui.page, "pos")
#        anim.setDuration(2000)
#        anim.setStartValue(QtCore.QPoint(self.ui.page.x(), self.ui.page.y() ))
#        anim.setEndValue(QtCore.QPoint(self.ui.page.x() -self.ui.page.width(), self.ui.page.y() ))
#        anim.setEasingCurve(QtCore.QEasingCurve.InOutBack)
#
#
#        anim2 = QtCore.QPropertyAnimation(self.ui.page_2, "pos")
#        anim2.setDuration(2000)
#        anim2.setStartValue(QtCore.QPoint(self.ui.page_2.x()+self.ui.page_2.width(), self.ui.page_2.y() ))
#        anim2.setEndValue(QtCore.QPoint(self.ui.page_2.x(), self.ui.page_2.y() ))
#        anim2.setEasingCurve(QtCore.QEasingCurve.InOutBack)
#
#
#        self.grp = QtCore.QParallelAnimationGroup()
#        self.grp.addAnimation(anim)
#        self.grp.addAnimation(anim2)
#        self.grp.start()
        
