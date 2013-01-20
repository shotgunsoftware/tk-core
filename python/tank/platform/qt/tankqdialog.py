"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Default implementation for the Tank Dialog

"""

from . import QtCore, QtGui
from . import ui_tank_dialog

TANK_TOOLBAR_HEIGHT = 45

class TankQDialog(QtGui.QDialog):
    """
    Wraps around app widgets. 
    """

    def __init__(self, widget, parent):
        QtGui.QDialog.__init__(self, parent)
        
        # set up the UI
        self.ui = ui_tank_dialog.Ui_TankDialog() 
        self.ui.setupUi(self)
        
        # parent the widget we are hosting into the dialog area
        widget.setParent(self.ui.page)
        self.ui.target.insertWidget(0, widget)
        
        # adjust size of the outer window to match the hosted widget size
        self.resize(widget.width(), widget.height() + TANK_TOOLBAR_HEIGHT)
        
        # intercept the close event of the child widget
        # so that when the close event is emitted from the hosted widget,
        # we make sure to clo
        widget.closeEvent = lambda event: self._handle_child_close(event)
        
    def _handle_child_close(self, event):
        event.accept()
        self.close()
        
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
        
