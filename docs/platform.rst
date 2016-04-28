.. currentmodule:: sgtk.platform

Toolkit Platform API
####################################################

This part of the API documentation covers all the classes and methods used when dealing with Engines, Apps and Frameworks.
If you are interested in developing your own apps, engines or frameworks, the base classes needed to be derived
from are outlined below. The documentation also covers how to initialize and shut down the Toolkit engine platform.

Launching and accessing the platform
---------------------------------------

The methods in this section are used when you want to start up or manage a Toolkit engine.
This typically happens directly once a host application (e.g. Maya or Nuke) has been launched.
A running engine typically needs to be terminated before a new engine can be started. The method
for terminating an engine can be found on the engine class itself.

.. autofunction:: start_engine

.. autofunction:: current_engine

.. autofunction:: get_engine_path

.. autofunction:: find_app_settings

.. autofunction:: change_context

.. autofunction:: restart


Engine
---------------------------------------

A toolkit engine connects a runtime environment such as a DCC with the rest of the Toolkit ecosystem.
As the engine starts up, it loads the various associated apps and frameworks defined in the configuration and acts a
host for all these objects, ensuring that they can operate in a consistent fashion across integrations.

**Information for App Developers**

If you are developing an app, you typically call out to the engine via the :meth:`Application.engine` accessor.
You use the engine for a couple of main things:

- Dialog UI creation via :meth:`Engine.show_dialog`, :meth:`Engine.show_modal` or :meth:`Engine.show_panel`

- Command registration via :meth:`Engine.register_command`

The engine takes acts as a bridge betgween the DCC and the App so that the app doesn't have to
contain DCC-specific code to create dialogs or manage menus etc. Typically, any DCC specific code
is contained within Hooks (or calling out to engine hooks), making it easy to design apps that
can be extended easily to support new engine environments.


**Information for Engine developers**

The engine is a collection of files, similar in structure to an App. It has an ``engine.py`` file and this must
derive from the :class:`Engine` Base class. Different engines then re-implement various aspect of this base
class depending on their internal complexity. A summary of functionality include:

- The base class exposes various init and destroy methods which are executed at various points in the startup
  process. These can be overridden to control startup and shutdown execution.

- The engine provides a commands dictionary containing all the command objects registered by apps.
  This is typically accessed when menu entries are created.

- Methods for displaying UI dialogs and windows can be overridden if the way the engine runs QT
  does not the default base class behavior.

The typical things an engine needs to handle are:

- Menu management. At engine startup, once the apps have been loaded, the engine needs to create
  its Shotgun menu and add the various apps to this menu.

- Logging methods are typically overridden to write to the application log.

- UI methods are typically overridden to ensure seamless integration of windows launched by Toolkit apps
  and the underlying host application window management setup. Engines are launched via the
  :meth:`stgk.platform.start_engine()` command. This command will read the configuration files,
  launch the engines, load all apps etc. The goal with the engine is that once it has launched,
  the it provides a consistent python/QT interface to the apps. Since all engines implement the
  same base class, apps can call methods on the engines to for example create UIs. It is up to each
  engine to implement these methods so that they work nicely inside the host application.



.. autoclass:: Engine
    :inherited-members:
    :exclude-members: descriptor, settings, get_env, log_metric, init_engine
    :members:


Application
---------------------------------------

.. autoclass:: Application
    :inherited-members:
    :exclude-members: descriptor, settings, get_env, log_metric
    :members:


Framework
---------------------------------------

Frameworks are like libraries. They contain functionality that can be shared and reused across apps or engines.

Frameworks are automatically imported into the system whenever Toolkit finds a framework defined in the info.yml
for an app or an engine. Once imported, it will be available in the frameworks dictionary on the host object.
For example, an app or engine (or framework) may have the following definition in its info.yml::

    frameworks:
        - {"name": "tk-framework-widget", "version": "v0.1.2"}
        - {"name": "tk-framework-tools", "version": "v0.x.x"}

When Toolkit loads the app, it will verify that the two frameworks are present in the environment and
initialize them. Once initialized, the app that needs them can access them via the ``self.frameworks``
property::

    foo_bar_module = self.frameworks["tk-framework-widget"].import_module("foo_bar")

In order to import a framework module into app or engine code, use the convenience method
:meth:`~sgtk.platform.import_framework`. This method is typically executed right in the beginning
of the file, before you create any methods or classes::

    import os
    import sys
    import sgtk
    widgets = sgtk.platform.import_framework("tk-framework-widget", "widgets")

    class MyBrowser(widgets.BrowserWidget):
        ...

If you would like to load the framework instance itself rather than a module which was imported as part of
the framework initalization, you can use the :meth:`~sgtk.platform.get_framework` method::

    import sgtk
    fw = sgtk.platform.get_framework("tk-framework-widget")

Note that this only works inside of code which has been imported via the import_module command - e.g.
the way we recommend that Sgtk code is being imported into apps. For other scenarios, use the frameworks
dictionary in conjunction with the import_module command, as shown above.

Frameworks are imported in an individual fashion, meaning that even though a framework is used in two apps,
each app will import its own instance of the framework. This is to ensure stability and encapsulation.

A framework works just like an app or an engine - it has an info.yml manifest, a framework.py file which
typically contains a class which derives from the Framework base class, etc.


.. autoclass:: Framework
    :inherited-members:
    :exclude-members: descriptor, settings, get_env, log_metric
    :members:

Exceptions
-----------------

.. autoclass:: TankEngineInitError

.. autoclass:: TankContextChangeNotSupportedError


Developing apps and engines
---------------------------------------


.. autofunction:: get_framework

.. autofunction:: import_framework

.. autofunction:: current_bundle




Using QT inside your app
---------------------------------------

You can use QT classes inside your app code. Sgtk will handle the import and gracefully manage different
platform considerations in the background. Typically, PySide is being used for QT integration, but Sgtk
may use PyQT in certain engines. Normally, the code is pretty portable between the two systems and it
should be no problem writing code that works with both libraries.

In order to use QT, import it from Sgtk::

    from sgtk.platform.qt import QtCore, QtGui

Toolkit will make sure Qt is sourced in the correct way. Keep in mind that many applications (for example Nuke)
may not have a functional Qt that can be imported when they run in batch mode.

When creating a dialog, it is important to parent it properly to the host environment. There is nothing stopping
you from managing this by yourself, but for maximum compatibility and portabilty, we strongly suggest that you l
et Toolkit handle it. When using Sgtk to set up your UI, just let your UI class derive from QtGui.QWidget and pass
it to one of the UI factory methods that the engine has. For example::

    from sgtk.platform.qt import QtCore, QtGui

    # derive from QtGui.QWidget for your UI components.

    class AppDialog(QtGui.QWidget):

        def __init__(self, param1, param2):
            QtGui.QWidget.__init__(self)

    # the engine is then used to correctly launch this dialog. In your app code
    # you can now do create a window using the engine's factory methods.

    # display widget in a modeless window:
    widget_obj = self.engine.show_dialog("Dialog Title", self, AppDialog, param1, param2)

    # display widget in a modal dialog - blocking call
    (return_code, widget_obj) = self.engine.show_modal("Dialog Title", self, AppDialog, param1, param2)

What happens in the above calls is that your app widget is parented inside of a Dialog window Sgtk is creating.
Sgtk will add additional potential window constructs, menus etc. Whenever the app widget is closed (for example
using the close() method), the parent window that is used to wrap the widget will automatically close too.

Modal dialogs and exit codes

If you want to run your widget as a modal dialog, it may be useful to signal success or failure.
This is normally done in QT using the methods QDialog.accepted() and QDialog.rejected(), however since the app
widget typically derives from QWidget, these methods are not available. Instead, Sgtk will look for a member
property called ``exit_code``. Typically, your code for a modal dialog would look something like this::

        def on_ok_button_clicked(self):
            # user clicked ok
            self.exit_code = QtGui.QDialog.Accepted
            self.close()

        def on_cancel_button_clicked(self):
            # user clicked cancel
            self.exit_code = QtGui.QDialog.Rejected
            self.close()

The call to self.engine.show_modal() will return the appropriate status code depending on which button was clicked.

Hiding the Sgtk Title Bar

By default, the standard Sgtk dialog includes a title bar at the top. However, sometimes this is not desirable,
especially when the contained widget is quite small. To hide the title bar, just add a property called
``hide_tk_title_bar`` to your widget class and set it to a value of True, for example::

    class MyWidget(QtGui.QWidget):

        @property
        def hide_tk_title_bar(self):
            return True

        def __init__(self):
            ...
