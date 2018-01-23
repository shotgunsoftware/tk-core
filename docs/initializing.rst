.. currentmodule:: sgtk.bootstrap

Initialization and startup
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

- The application bundles that are required can be stored anywhere on the local machine or the
  network via the use of the ``SHOTGUN_BUNDLE_CACHE_FALLBACK_PATHS`` environment variable.

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
    :show-inheritance:
    :inherited-members:
    :members:

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



Launching and initializing
--------------------------

Toolkit can be launched and started up in two fundamentally different ways:

- All configurations can be started up via the :class:`~sgtk.bootstrap.ToolkitManager` bootstrap API. This
  API abstracts the entire process of initialization and provides a consistent set of methods for all
  projects and configurations. This is the recommended way to launch toolkit and gain access to a running
  Toolkit :class:`~sgtk.platform.Engine` instance (which in turn contains a :class:`sgtk.Sgtk` instance.

- Configurations which have been installed into a specific location via the ``tank setup_project`` command
  or via Shotgun Desktop's setup wizard can be initialized in additional ways. Such setups are referred to
  as 'classic' toolkit setups. For most scenarios, we recommend using the :class:`~sgtk.bootstrap.ToolkitManager`
  for access.

Factory methods for classic configurations
==========================================

.. currentmodule:: sgtk

For classic configurations, where the configuration resides in a specific location on disk, you can use
the following factory methods to create a :class:`sgtk.Sgtk` instance:

.. autofunction:: sgtk_from_path
.. autofunction:: sgtk_from_entity

.. note::
    You can also use the methods above in conjunction with projects handled
    by the :class:`~sgtk.bootstrap.ToolkitManager`, but since the location
    of the configuration of such projects isn't explicit and known beforehand,
    the factory methods are less useful in this context.







Launching Software
---------------------------------------------------

.. currentmodule:: sgtk.platform

In order to run software integrations in the form of a Toolkit :class:`Engine`,
it is necessary to be able to easily launch the software and initialize Toolkit once
the software environment.

Toolkit offers a centralized set of APIs to make this task straight forward. Each engine
implements the following:

- How installed versions of the software are auto-detected
- How to launch the software and what environment to pass
- How to make sure the toolkit integration auto-loads once the software has launched.

.. note:: These APIs can be wrapped inside a Toolkit app or simliar in order
    to create a centralized launcher experience. The ``tk-multi-launchapp`` is
    an example of such an implementation.


A Simple Launch Application
===================================================

The Toolkit core API provides an interface that custom applications can use to implement the business
logic for launching DCC software related to a particular Toolkit engine. This interface is comprised
of a factory method :meth:`create_engine_launcher` and classes :class:`SoftwareLauncher`,
:class:`SoftwareVersion`, and :class:`LaunchInformation`. The factory method is called for a specific
engine in the environment configuration and returns a SoftwareLauncher subclass instance implemented
by that engine.

Methods on the launcher instance can be used to determine which versions of the DCC
are installed on the local filesystem and the proper environment, including command line arguments,
required for a successful launch.

The following lines of python code demonstrate how to launch Maya using the core interface::

    import subprocess
    import sgtk

    # Create a Toolkit Core API instance based on a project path or
    # path that points directly at a pipeline configuration.
    tk = sgtk.sgtk_from_path("/site/project_root")

    # Specify the context the DCC will be started up in.
    context = tk.context_from_path("/site/project_root/sequences/AAA/ABC/Light/work")

    # Using a core factory method, construct a SoftwareLauncher
    # subclass for the desired tk engine.
    software_launcher = sgtk.platform.create_engine_launcher(tk, context, "tk-maya")

    # Use the SoftwareLauncher instance to find a list of Maya versions installed on the
    # local filesystem. A list of SoftwareVersion instances is returned.
    software_versions = software_launcher.get_supported_software()

    # Ask the SoftwareLauncher instance to prepare an environment to launch Maya in.
    # For simplicity, use the first version returned from the list of software_versions.
    launch_info = software_launcher.prepare_launch(software_versions[0].path)

    # Launch Maya!
    launch_command = "%s %s" % (launch_info.path, launch_info.args)
    subprocess.Popen([launch_command], env=launch_info.environment)


Engine Implementation
===================================================

To plug into the core API software launch interface, a Toolkit engine must implement a subclass of
:class:`SoftwareLauncher` in a ``startup.py`` file at the engine root level, analogous to the
``engine.py`` file.

Scripts required by the engine to prepare the launch environment
or initialize the engine once the DCC has started up typically reside under a sibiling ``startup``
directory:

.. image:: ./resources/tk_engine_root_directory_structure.png

Since the launch logic for the engine is invoked while the engine is not actually running, the
:class:`~SoftwareLauncher` base class provides functionality similar to the :class:`~Engine` base
class. Two SoftwareLauncher methods that *must* be implemented by an engine are :meth:`~SoftwareLauncher.scan_software`
and :meth:`~SoftwareLauncher.prepare_launch`.

The :meth:`~SoftwareLauncher.scan_software` method is responsible for discovering the executable paths for the related DCC
installed on the local filesystem and returns a list of :class:`SoftwareVersion` instances representing
the executables found.

The :meth:`~SoftwareLauncher.prepare_launch` method establishes the environment to launch the DCC in, confirms the correct
executable path to launch, and supplies command line arguments required for launch. This method returns a
:class:`LaunchInformation` instance that contains all information required to successfully launch the
DCC and startup the engine integration.

:meth:`~SoftwareLauncher.prepare_launch` method must assure the paths to ``sgtk`` and any
startup files are specified in the ``PYTHONPATH`` environment variable. For example, the Maya engine
contains a ``userSetup.py`` file located in a ``startup`` folder inside the engine. the
:meth:`~SoftwareLauncher.prepare_launch` adds this path to the ``PYTHONPATH``, thereby ensuring that
once maya has been launched, execution continues in this file.


To recap, a skeleton ``startup.py`` file for the Maya engine contains the following::

    from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation

    class MayaLauncher(SoftwareLauncher):

        def scan_software(self):
            # Construct a list of SoftwareVersion instances representing executable versions of the DCC
            # installed on the local filesystem.
            software_versions = []
            ...
            return software_versions

        def prepare_launch(self, exec_path, args, file_to_open=None):
            # Construct an environment to launch the DCC in, confirm the correct executable path to
            # launch, and provide required command line args. Return this information as a
            # LaunchInformation instance.
            correct_executable_path = ""
            command_line_args = ""
            launch_environment = {}
            ...
            launch_information = LaunchInformation(correct_executable_path, command_line_args, launch_environment)
            return launch_information





.. note:: How to initialize and runs code at startup will vary from DCC to DCC.
    The supported toolkit engines for Maya, Nuke, and Houdini are good reference implementations.

.. note:: When setting an environment variable containing the current context value, be sure to use a
    serialized version of the context to encode login information in the shell.



Software Launch APIs
============================



This section contains the techincal documentation for the core classes and methods described in the
:ref:`Launching Software` section above.

.. autofunction:: create_engine_launcher

SoftwareLauncher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: SoftwareLauncher
  :members:
  :exclude-members: descriptor,
                    settings

  The following methods can be used by subclasses to help implement :meth:`scan_software`.

  .. automethod:: _is_supported
  .. automethod:: _glob_and_match

SoftwareVersion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: SoftwareVersion
    :members:

LaunchInformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: LaunchInformation
    :members:

