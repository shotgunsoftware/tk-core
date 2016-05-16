.. currentmodule:: sgtk.bootstrap

Deploy and Management
########################################

This section outlines the various ways to set up, configure and initialize a Toolkit Setup.
There are two fundamental approaches to running Toolkit: A traditional project based setup
and a :class:`ToolkitManager` API that allows for more flexible manipulation of
configurations and installations.

Traditional Project Setup
----------------------------------------

The traditional Toolkit 'pipeline approach' means that you pick an existing Shotgun
project and run a Toolkit project setup for this project. This is typically done in
Shotgun Desktop or via the ``tank setup_project`` command. A toolkit configuration
is installed in a shared location on disk and a pipeline configuation in Shotgun is
created to create an association between the installation on disk and the project in
Shotgun.

Once the installation has completed, you can access functionality via the ``tank`` command
for that project or run :meth:`sgtk.sgtk_from_entity()` or :meth:`sgtk.sgtk_from_path()`
in order to create an API session, associated with the project configuration.


Bootstrapping Toolkit
----------------------------------------

An alternative to the traditional project based setup was introduced in Core v0.18 - the
:class:`ToolkitManager` class allows for more flexible manipulation of toolkit setups
and removes the traditional step of a project setup. Instead, you can launch an engine
straight directly based on a toolkit configuration. The manager encapsulates the deploy
and configuration management process and makes it easy to create a running instance of
Toolkit. It allows for several advanced use cases:

- Bootstrapping via the toolkit manager does not require anything to be
  set up or configured in Shotgun. No extensive project setup step is required.

- A setup can be pre-bundled with for example an application plugin, allowing
  Toolkit to act as a distribution platform.

- The toolkit manager makes it easy to track remote resources (via the ``sgtk.descriptor``
  framework).

The following example code can for example run inside maya in order
to launch toolkit's default config for a given Shotgun Asset::

    import sgtk

    # let the user select a site and log in
    sg_auth = sgtk.authentication.ShotgunAuthenticator()
    user = sg_auth.get_user()

    # start up a Toolkit Manager
    mgr = sgtk.bootstrap.ToolkitManager(user)

    # set the base configuration to the default config
    mgr.base_configuration = "sgtk:descriptor:app_store?name=tk-config-default"

    # make sure we grab the latest version
    mgr.resolve_latest_base_configuration = True

    # now start up the maya engine for a given shotgun object
    e = mgr.bootstrap_engine("tk-maya", entity={"type": "Asset", "id": 1234})

Note that the example is primitive and for example purposes only as it will take time to execute
and blocks execution during this period.

In this example, there is no need to construct any :class:`sgtk.Sgtk` instance or run a ``tank``
command - the :class:`ToolkitManager` instead becomes the entry point into the system. It will
handle the setup and initialization of the configuration behind the scenes
and start up a Toolkit session once all the required pieces have been initialized and set up.

ToolkitManager
========================================

.. autoclass:: ToolkitManager
    :members:
    :inherited-members:

Exception Classes
========================================

.. autoclass:: TankBootstrapError


