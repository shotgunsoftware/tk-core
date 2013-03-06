"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Default implementation for the Tank Dialog

"""

from . import QtCore, QtGui
from . import ui_tank_dialog
from . import TankDialogBase
from .config_item import ConfigItem
from .. import engine

import sys
import os

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
        
        # indicates that we are showing the info pane
        self._info_mode = False
        self._bundle = bundle
        
        self._config_items = []
        
        ########################################################################################
        # set up the main UI and header
        
        self.ui = ui_tank_dialog.Ui_TankDialog() 
        self.ui.setupUi(self)
        self.ui.label.setText(title)
        self.setWindowTitle("Tank: %s" % title)
        
        self.ui.tank_logo.setToolTip("This is part of the Tank App %s" % self._bundle.name)
        self.ui.label.setToolTip("This is part of the Tank App %s" % self._bundle.name)
        
        # Add our context to the header
        self.ui.lbl_context.setText( "Current Work Area:\n%s" % self._bundle.context)

        ########################################################################################
        # add more detailed context info for the tooltip

        def _format_context_property(p, show_type=False):
            if p is None:
                return "Undefined"
            elif show_type:
                return "%s %s" % (p["type"], p["name"])
            else:
                return "%s" % p["name"]
    
        tooltip = "<b>Work Area Details:</b>"
        tooltip += "<br><b>Project</b>: %s" % _format_context_property(self._bundle.context.project)
        tooltip += "<br><b>Item</b>: %s" % _format_context_property(self._bundle.context.entity, True)
        tooltip += "<br><b>Pipeline Step</b>: %s" % _format_context_property(self._bundle.context.step)
        tooltip += "<br><b>Task</b>: %s" % _format_context_property(self._bundle.context.task)
        tooltip += "<br><b>User</b>: %s" % _format_context_property(self._bundle.context.user)
        for e in self._bundle.context.additional_entities:
            tooltip += "<br><b>Additional Item</b>: %s" % _format_context_property(e, True) 
        self.ui.lbl_context.setToolTip(tooltip)
        
        ########################################################################################
        # parent the widget we are hosting into the dialog area
        
        widget.setParent(self.ui.page_1)
        self.ui.target.insertWidget(0, widget)
        # keep track of the widget
        self._widget = widget
        
        # adjust size of the outer window to match the hosted widget size
        self.resize(widget.width(), widget.height() + TANK_TOOLBAR_HEIGHT)
        
        ########################################################################################
        # intercept the close event of the child widget
        # so that when the close event is emitted from the hosted widget,
        # we make sure to clo
        
        widget.closeEvent = lambda event: self._handle_child_close(event)
        
        
        ########################################################################################
        # now setup the info page with all the details
        
        self.ui.details.clicked.connect( self._on_arrow )
        self.ui.app_name.setText(self._bundle.display_name)
        self.ui.app_description.setText(self._bundle.description)
        # get the descriptor type (eg. git/app store/dev etc)
        descriptor_type = self._bundle.descriptor.get_location().get("type", "Undefined")
        self.ui.app_tech_details.setText("%s %s (Source: %s)" % (self._bundle.name, 
                                                                 self._bundle.version,
                                                                 descriptor_type))

        context_info = "Your current work area is %s. " % self._bundle.context
        try:
            # try get the environment - may not work - not all bundle classes have a .engine method
            context_info += "You are currently running Tank in the %s environment." % (self._bundle.engine.environment["name"])
        except:
            pass
        self.ui.app_work_area_info.setText(context_info)

        # see if there is an app icon, in that case display it
        self.ui.app_icon.setPixmap(QtGui.QPixmap(self._bundle.icon_256))        

        self.ui.btn_documentation.clicked.connect( self._on_doc )
        self.ui.btn_support.clicked.connect( self._on_support )
        self.ui.btn_file_system.clicked.connect( self._on_filesystem )
        self.ui.btn_shotgun.clicked.connect( self._on_shotgun )
        self.ui.btn_reload.clicked.connect( self._on_reload )
        self.ui.btn_edit_config.clicked.connect( self._on_edit_config )
        self.ui.btn_add_parameter.clicked.connect( self._on_add_param )
        
        self.ui.btn_edit_config.setVisible(False)
        self.ui.btn_add_parameter.setVisible(False)
        
        for setting, params in self._bundle.descriptor.get_configuration_schema().items():        
            value = self._bundle.settings.get(setting)
            self._add_settings_item(setting, params, value)
        
        
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
        
    def _on_arrow(self):
        """
        callback when someone clicks the 'details' > arrow icon
        """
        GRADIENT_WIDTH = 11
        INFO_WIDTH = 400
        
            
        if self._info_mode:
            # activate page 1 again - note that this will reset all positions!
            self.ui.stackedWidget.setCurrentIndex(0)
            # this hides page page 2, but let's show it again
            self.ui.page_2.show()
            
            self.anim = QtCore.QPropertyAnimation(self.ui.page_1, "pos")
            self.anim.setDuration(800)
            self.anim.setStartValue(QtCore.QPoint(self.ui.page_1.x()-(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_1.y() ))
            self.anim.setEndValue(QtCore.QPoint(self.ui.page_1.x(), self.ui.page_1.y() ))
            self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self.anim.finished.connect( self._finished_show_anim )

            self.anim2 = QtCore.QPropertyAnimation(self.ui.page_2, "pos")
            self.anim2.setDuration(800)
            self.anim2.setStartValue(QtCore.QPoint(self.ui.page_2.x(), self.ui.page_2.y() ))
            self.anim2.setEndValue(QtCore.QPoint(self.ui.page_2.x()+GRADIENT_WIDTH+INFO_WIDTH, self.ui.page_2.y() ))
            self.anim2.setEasingCurve(QtCore.QEasingCurve.OutCubic)

            self.grp = QtCore.QParallelAnimationGroup()
            self.grp.addAnimation(self.anim)
            self.grp.addAnimation(self.anim2)
            self.grp.start()            

            
        else:
            
            # activate page 2 - note that this will reset all positions!
            self.ui.stackedWidget.setCurrentIndex(1)
            # this hides page page 1, but let's show it again
            self.ui.page_1.show()
            # but make sure page1 stays on top
            self.ui.page_1.raise_()                

            self.anim = QtCore.QPropertyAnimation(self.ui.page_2, "pos")
            self.anim.setDuration(800)
            self.anim.setStartValue(QtCore.QPoint(self.ui.page_2.x()+(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_2.y() ))
            self.anim.setEndValue(QtCore.QPoint(self.ui.page_2.x(), self.ui.page_2.y() ))
            self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
    
            self.anim2 = QtCore.QPropertyAnimation(self.ui.page_1, "pos")
            self.anim2.setDuration(800)
            self.anim2.setStartValue(QtCore.QPoint(self.ui.page_1.x(), self.ui.page_1.y() ))
            self.anim2.setEndValue(QtCore.QPoint(self.ui.page_1.x()-(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_1.y() ))
            self.anim2.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self.anim2.finished.connect( self._finished_show_anim )
            
            self.grp = QtCore.QParallelAnimationGroup()
            self.grp.addAnimation(self.anim)
            self.grp.addAnimation(self.anim2)
            self.grp.start()            

    def _finished_show_anim(self):
        """
        Callback called when the animation is complete
        """
        # now set the new info mode representing 
        # the state we have just arrived at
        self._info_mode = not(self._info_mode)
        
        if not self._info_mode:
            # no longer want to display the side bar
            self.ui.page_2.hide()

    def _on_doc(self):
        """
        Launch doc url
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._bundle.documentation_url))

    
    def _on_support(self):
        """
        Launch support url
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._bundle.support_url))

    def _on_filesystem(self):
        """
        Show the context in the file system
        """
        # launch one window for each location on disk        
        paths = self._bundle.context.filesystem_locations
        for disk_location in paths:
                
            # get the setting        
            system = sys.platform
            
            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)
            
            exit_code = os.system(cmd)
            if exit_code != 0:
                self._engine.log_error("Failed to launch '%s'!" % cmd)
        

    def _on_shotgun(self):
        """
        Show the context in shotgun
        """
        url = self._bundle.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


    def _on_reload(self):
        """
        Reloads the engine and apps
        """
        try:
            current_context = self._bundle.context            
            current_engine_name = self._bundle.engine.name
            if engine.current_engine(): 
                engine.current_engine().destroy()
            engine.start_engine(current_engine_name, current_context.tank, current_context)
        except Exception, e:
            self._bundle.log_exception("Could not restart the engine!")


    def _on_edit_config(self):
        """
        Future use
        """
        pass

    def _on_add_param(self):
        """
        Future use
        """
        pass

    def _add_settings_item(self, setting, params, value):
        """
        Adds a settings item to the list of settings.
        """
        widget = ConfigItem(setting, params, value, self._bundle, self)
        self.ui.config_layout.addWidget(widget)
        self._config_items.append(widget)   
        
