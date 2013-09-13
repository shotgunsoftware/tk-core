# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Default implementation for the Tank Dialog

"""

from . import QtCore, QtGui
from . import ui_tank_dialog
from . import TankDialogBase
from .config_item import ConfigItem
from .. import engine
from .. import application
from .. import constants
from ...errors import TankError

import sys
import os
import inspect

TANK_TOOLBAR_HEIGHT = 45

class TankQDialog(TankDialogBase):
    """
    Wraps around app widgets. Contains Tank specific toolbars and configuration info
    in addition to the user object that it is hosting.
    """

    @staticmethod
    def _stop_pre_v0_1_17_browser_widget_workers(widget):
        """
        Determine if a pre-v0.1.17 tk-framework-widget BrowserWidget exists within the
        dialog.
        
        There is a bug in the worker/threading code in the BrowserWidget that was fixed
        in v0.1.17.  This would result in a fatal crash if the BrowserWidget was cleaned 
        up properly!  
        
        However, because the engine was previously not releasing any dialogs, the cleanup 
        code was never running which meant the bug was hidden!
        
        Now the engine has been fixed so that it cleans up correctly, all old versions 
        of apps using a pre-v0.1.17 version of the BrowserWidget have become extremely 
        unstable.
        
        As a workaround, this function finds all pre-v0.1.17 BrowserWidgets and applies
        the fix (basically waits for the worker thread to stop) to avoid instability!
        """
        checked_classes = {}
        
        widgets = [widget]
        for w in widgets:
            
            # look through class hierarchy - can't use isinstance here 
            # because we don't know which module the BrowserWidget would
            # be from! 
            is_browser_widget = False
            for cls in inspect.getmro(type(w)):
                
                checked_result = checked_classes.get(cls, None)
                if checked_result != None:
                    is_browser_widget = checked_result
                    break 
                
                checked_classes[cls] = False
                    
                # only care about classes explicitly called 'BrowserWidget':
                if cls.__name__ != "BrowserWidget":
                    continue
                    
                # check the class has some members we know about:
                if (not hasattr(w, "_worker") or not isinstance(w._worker, QtCore.QThread)
                    or not hasattr(w, "_app") or not isinstance(w._app, application.Application)
                    or not hasattr(w, "_spin_icons") or not isinstance(w._spin_icons, list)):
                    continue
    
                # ok, so we can assume this widget is derived from a 
                # tk-framework-widget BrowserWidget
                checked_classes[cls] = True
                is_browser_widget = True                    
                break
                
            if is_browser_widget:
    
                # lets see if it contains the threading fix...
                if hasattr(w, "_TK_FRAMEWORK_BROWSERWIDGET_HAS_V_0_1_17_THREADING_FIX__"):
                    # this is already fixed so we don't need to do anything more!
                    continue
                
                # so this is a pre v0.1.17 version of the BrowserWidget so
                # lets make sure the worker is stopped...
                w._worker.stop()
                # and wait for the thread to finish - this line is the fix!
                w._worker.wait()
    
            else:
                # add all child widgets to list to be checked
                widgets.extend(w.children())


    @staticmethod
    def wrap_widget_class(widget_class):
        """
        Return a new class derived from widget_class that overrides
        the closeEvent method and emits a signal if the event is
        accepted by the widget_class implementation.
        
        This is the cleanest way I've found to catch when the widget
        has been closed that doesn't mess with either Qt or Python
        memory/gc management!
        """
        derived_class_name = "__" + widget_class.__name__ + "_TkWidgetWrapper__"
        def closeEvent(self, event):
            """
            close event handled for the wrapper class.  This
            calls the widget_class.closeEvent method and then
            if the event was accepted it emits the widget
            closed signal.
            """
            # call base class closeEvent:
            widget_class.closeEvent(self, event)
            
            # apply fix to make sure all workers in pre v0.1.17 tk-framework-widget
            # BrowserWidgets are stopped correctly!
            TankQDialog._stop_pre_v0_1_17_browser_widget_workers(self)
            
            # if accepted then emit signal:            
            if event.isAccepted():
                self._tk_widgetwrapper_widget_closed.emit()
        
        # create the derived widget class:
        derived_widget_class = type(derived_class_name, (widget_class, ), 
                                    {"_tk_widgetwrapper_widget_closed":QtCore.Signal(), 
                                     "closeEvent":closeEvent})
        return derived_widget_class
    
    # Signal emitted when dialog is closed
    # either via closing the dialog directly
    # or as a result of the child widget 
    # being closed.
    dialog_closed = QtCore.Signal(object)    

    def __init__(self, title, bundle, widget, parent):
        """
        Constructor
        """
        TankDialogBase.__init__(self, parent)
        
        # indicates that we are showing the info pane
        self._info_mode = False
        self._bundle = bundle
        self._widget = widget
        
        self._config_items = []
        
        ########################################################################################
        # set up the main UI and header
        
        self.ui = ui_tank_dialog.Ui_TankDialog() 
        self.ui.setupUi(self)
        self.ui.label.setText(title)
        self.setWindowTitle("Shotgun: %s" % title)
        
        self.ui.tank_logo.setToolTip("This is part of the Shotgun App %s" % self._bundle.name)
        self.ui.label.setToolTip("This is part of the Shotgun App %s" % self._bundle.name)
        
        # Add our context to the header
        # two lines - top line covers PC and Project
        # second line covers context (entity, step etc)
        
        pc = self._bundle.context.tank.pipeline_configuration
        
        if self._bundle.context.entity is None:
            # this is a project only context
            
            # top line can contain the Pipeline Config
            if pc.get_name() and pc.get_name() != constants.PRIMARY_PIPELINE_CONFIG_NAME:
                # we are using a non-default pipeline config
                first_line = "<b style='color: #9cbfff'>Config %s</b>" % pc.get_name()
            else:
                first_line = "Toolkit %s" % self._bundle.context.tank.version
            
            # second line contains the project
            if self._bundle.context.project:
                second_line = "Project %s" % self._bundle.context.project.get("name", "Undefined")
            else:
                second_line = "No Project Set"
            
        else:
            # this is a standard context with an entity
            
            # top line will contain the project name
            if self._bundle.context.project:
                first_line = "Project %s" % self._bundle.context.project.get("name", "Undefined")
            else:
                first_line = "No Project Set" # can this happen?
            
            # ...unless we are running a non-Primary PC
            pc = self._bundle.context.tank.pipeline_configuration 
            if pc.get_name() and pc.get_name() != constants.PRIMARY_PIPELINE_CONFIG_NAME:
                # we are using a non-default pipeline config
                first_line = "<b style='color: #9cbfff'>Config %s</b>" % pc.get_name() 
            
            # second line contains the entity and task, step
            second_line = str(self._bundle.context)

        
        self.ui.lbl_context.setText( "%s<br>%s" % (first_line, second_line))

        ########################################################################################
        # add more detailed context info for the tooltip

        def _format_context_property(p, show_type=False):
            if p is None:
                return "Undefined"
            elif show_type:
                return "%s %s" % (p.get("type"), p.get("name"))
            else:
                return "%s" % p.get("name")
    
        tooltip = ""
        tooltip += "<b>Your Current Context</b>"
        tooltip += "<hr>"
        tooltip += "<b>Project</b>: %s<br>" % _format_context_property(self._bundle.context.project)
        tooltip += "<b>Entity</b>: %s<br>" % _format_context_property(self._bundle.context.entity, True)
        tooltip += "<b>Pipeline Step</b>: %s<br>" % _format_context_property(self._bundle.context.step)
        tooltip += "<b>Task</b>: %s<br>" % _format_context_property(self._bundle.context.task)
        tooltip += "<b>User</b>: %s<br>" % _format_context_property(self._bundle.context.user)
        for e in self._bundle.context.additional_entities:
            tooltip += "<b>Additional Item</b>: %s<br>" % _format_context_property(e, True) 
        
        tooltip += "<br>"
        tooltip += "<b>System Information</b>"
        tooltip += "<hr>"
        tooltip += "<b>Shotgun Pipeline Toolkit Version: </b>%s<br>" % self._bundle.tank.version
        tooltip += "<b>Pipeline Config: </b>%s<br>" % pc.get_name()
        tooltip += "<b>Config Path: </b>%s<br>" % pc.get_path()
        
        self.ui.lbl_context.setToolTip(tooltip)
        
        ########################################################################################
        # parent the widget we are hosting into the dialog area
        
        self._widget.setParent(self.ui.page_1)
        self.ui.target.insertWidget(0, self._widget)
        
        # adjust size of the outer window to match the hosted widget size
        self.resize(self._widget.width(), self._widget.height() + TANK_TOOLBAR_HEIGHT)
        
        ########################################################################################
        # keep track of widget so that when
        # it closes we also close this dialog
        self._orig_widget_closeEvent = None
        if hasattr(self._widget, "_tk_widgetwrapper_widget_closed"):
            # This is a wrapped widget so we can cleanly connect to the closed
            # signal it provides.
            #
            # Doing things this way will result in gc being able to clean up
            # properly when the widget object is no longer referenced!
            self._widget._tk_widgetwrapper_widget_closed.connect(self._on_widget_closed)
        else:
            # This is a non-wrapped widget so lets use the less
            # memory friendly version by bypassing the closeEvent method!
            # Note, as soon as we do this, python thinks there is a circular 
            # reference between the widget and the bound method so it won't clean
            # it up straight away...
            #
            # If widget also has a __del__ method then this will stop it 
            # being gc'd at all!
            self._orig_widget_closeEvent = self._widget.closeEvent
            self._widget.closeEvent = self._widget_closeEvent
        
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
        # try get the environment - may not work - not all bundle classes have a .engine method
        try:
            context_info += "You are currently running in the %s environment." % (self._bundle.engine.environment["name"])
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

    def done(self, exit_code):
        """
        Override 'done' method to emit dialog_closed
        event.  This method is called regardless of
        how the dialog is closed.
        """
        if self._widget:
            # detach the widget:
            self._detach_widget(True)
        
        # call base implementation:
        TankDialogBase.done(self, exit_code)

        # and emit signal:
        self.dialog_closed.emit(self)
          
    def _detach_widget(self, close_widget):
        """
        Detach the widget from the dialog so that it 
        remains alive when the dialog is removed/closed
        """
        if not self._widget:
            return
        
        # stop watching for the widget being closed:
        if hasattr(self._widget, "_tk_widgetwrapper_widget_closed"):
            # disconnect from the widget closed signal
            self._widget._tk_widgetwrapper_widget_closed.disconnect(self._on_widget_closed)
            
        elif self._orig_widget_closeEvent:
            # apply fix to make sure all workers in pre v0.1.17 tk-framework-widget
            # BrowserWidgets are stopped correctly!
            # Note, this is the only place this can be done for non-wrapped
            # widgets as once it's detached we have no further access to it!
            TankQDialog._stop_pre_v0_1_17_browser_widget_workers(self)
            
            # reset the widget closeEvent function.  Note that 
            # python still thinks there is a circular reference
            # (inst->bound method->inst) so this will get gc'd 
            # but not straight away!
            self._widget.closeEvent = self._orig_widget_closeEvent
            self._orig_widget_closeEvent = None
        
        # unparent the widget from the dialog:
        if self._widget.parent() == self.ui.page_1:
            self._widget.setParent(None)
            
        if close_widget:
            # close the widget - this makes sure that the closeEvent event
            # in the widget is triggered:
            self._widget.close()
            
            # finally, if there are no other references to widget
            # then we need to call deleteLater.  The is because
            # there may still be events waiting to be sent to the 
            # widget which will cause a crash if the widget is gc'd
            # before the events are sent.  deleteLater clears the
            # event queue for all events with the widget (and 
            # children) as the reciever stopping these crashes!
            #
            # Note, it seems that this scenario only happens if
            # _detach_widget(True) executes as a result of another
            # signal, e.g. key-press for the escape key causing
            # the dialog to be closed.
            if sys.getrefcount(self._widget) <= 2:
                self._widget.deleteLater()
            
        self._widget = None
        
    def _widget_closeEvent(self, event):
        """
        Called if the contained widget isn't a wrapped widget
        and it's closed by calling widget.close()
        """
        if self._orig_widget_closeEvent:
            # call the original closeEvent
            self._orig_widget_closeEvent(event)

        if not event.isAccepted():
            # widget didn't accept the close
            # so stop!
            return
        
        # the widget is going to close so
        # lets handle it!
        self._on_widget_closed()
        
    def _on_widget_closed(self):
        """
        This is called when the contained widget
        is closed - it handles the event and then
        closes the dialog
        """
        exit_code = QtGui.QDialog.Accepted
        
        # look if the hosted widget has an exit_code we should pick up
        if self._widget and hasattr(self._widget, "exit_code"):
            exit_code = self._widget.exit_code        
        
        # detach the widget from the dialog:
        self._detach_widget(False)
        
        # and call done to close the dialog with
        # the correct exit code
        self.done(exit_code)

    def _on_arrow(self):
        """
        callback when someone clicks the 'details' > arrow icon
        """
        GRADIENT_WIDTH = 11
        INFO_WIDTH = 400
        
            
        if self._info_mode:
            
            self.setUpdatesEnabled(False)
            try:
                # activate page 1 again - note that this will reset all positions!
                self.ui.stackedWidget.setCurrentIndex(0)
                # this hides page page 2, but let's show it again
                self.ui.page_2.show()
                # put this window top most to avoid flickering
                self.ui.page_2.raise_()       
                # and move the page 1 window back to its current position
                self.ui.page_1.move( self.ui.page_1.x()-(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_1.y())
                # now that the first window is positioned correctly, make it top most again.
                self.ui.page_1.raise_()       
            finally:
                self.setUpdatesEnabled(True)
            
            self.anim = QtCore.QPropertyAnimation(self.ui.page_1, "pos")
            self.anim.setDuration(600)
            self.anim.setStartValue(QtCore.QPoint(self.ui.page_1.x(), self.ui.page_1.y() ))
            self.anim.setEndValue(QtCore.QPoint(self.ui.page_1.x()+(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_1.y() ))
            self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self.anim.finished.connect( self._finished_show_anim )

            self.anim2 = QtCore.QPropertyAnimation(self.ui.page_2, "pos")
            self.anim2.setDuration(600)
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
            self.anim.setDuration(600)
            self.anim.setStartValue(QtCore.QPoint(self.ui.page_2.x()+(GRADIENT_WIDTH+INFO_WIDTH), self.ui.page_2.y() ))
            self.anim.setEndValue(QtCore.QPoint(self.ui.page_2.x(), self.ui.page_2.y() ))
            self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
    
            self.anim2 = QtCore.QPropertyAnimation(self.ui.page_1, "pos")
            self.anim2.setDuration(600)
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
        except TankError, e:
            self._bundle.log_error("Could not restart the engine: %s" % e)
        except Exception:
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
        
