.. currentmodule:: sgtk.bootstrap

Deploy and management
########################################

This section outlines the various ways to set up, configure and initialize a Toolkit Setup.
There are two fundamental approaches to running Toolkit: A traditional project based setup
and a :class:`ToolkitManager` API that allows for more flexible manipulation of
configurations and installations.

Traditional project setup
----------------------------------------

The traditional Toolkit 'pipeline approach' means that you pick an existing Shotgun
project and run a Toolkit project setup for this project. This is typically done in
Shotgun Desktop or via the ``tank setup_project`` command. A Toolkit configuration
is installed in a shared location on disk and a pipeline configuration in Shotgun is
created to create an association between the installation on disk and the project in
Shotgun.

Once the installation has completed, you can access functionality via the ``tank`` command
for that project or run :meth:`sgtk.sgtk_from_entity()` or :meth:`sgtk.sgtk_from_path()`
in order to create an API session.

Bootstrapping Toolkit
----------------------------------------

An alternative to the traditional project based setup was introduced in Core v0.18 - the
:class:`ToolkitManager` class allows for more flexible manipulation of toolkit setups
and removes the traditional step of a project setup. Instead, you can launch an engine
straight directly based on a Toolkit configuration. The manager encapsulates the deploy
and configuration management process and makes it easy to create a running instance of
Toolkit. It allows for several advanced use cases:

- Bootstrapping via the Toolkit manager does not require anything to be
  set up or configured in Shotgun. No extensive project setup step is required.

- A setup can be pre-bundled with for example an application plugin, allowing
  Toolkit to act as a distribution platform.

- The Toolkit manager makes it easy to track remote resources (via the ``sgtk.descriptor``
  framework).

The following example code can for example run inside maya in order
to launch Toolkit's default config for a given Shotgun Asset::

    import sgtk

    # Start up a Toolkit Manager
    mgr = sgtk.bootstrap.ToolkitManager()

    # Set the base configuration to the default config
    # note that the version token is not specified
    # The bootstrap will always try to use the latest version
    mgr.base_configuration = "sgtk:descriptor:app_store?name=tk-config-default"

    # now start up the maya engine for a given Shotgun object
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
    :exclude-members: entry_point, set_progress_callback

Exception Classes
========================================

.. autoclass:: TankBootstrapError


Installing the sgtk module using pip
----------------------------------------

When running Toolkit using the bootstrap API above, you need access to the :class:`ToolkitManager`
class in order to kickstart the bootstrap process. Once you have started the bootstrap, toolkit will
download all the necessary components for the given configuration you are bootstrapping into,
potentially even including a different version of the core API than you are using to bootstrap with.

In order to fully automate this process programatically, you need an ``sgtk`` instance to begin with.
One way to accomplish this is to use ``pip`` (see https://pip.pypa.io/). Use the following syntax::

    pip install git+https://github.com/shotgunsoftware/tk-core@v0.18.35


If you want to add an sgtk core to a ``requirements.txt`` file, use the following syntax::

    git+https://github.com/shotgunsoftware/tk-core@v0.18.35

.. warning:: In order to use ``pip``, you currently need to have the git executable installed
             on the system that you are deploying to.

.. warning:: We strongly recommend always providing a version number. Not providing a version
             number will currently download the latest commit from the master branch and
             associate it with the highest available version number tag. Such downloads are
             likely to contain changes which have not yet been full tested.

