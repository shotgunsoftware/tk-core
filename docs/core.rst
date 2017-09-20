.. currentmodule:: sgtk

Foundation
########################################

The Toolkit Foundation is the part of the Toolkit Core API
that contains lower level components and APIs. These include

- Automatic folder creation
- :class:`Template` system and path resolution APIs
- Execution of Tank Admin commands
- The Toolkit :class:`Context`
- The :class:`Sgtk` Main API class


For apps and engines, see the :ref:`sgtk_platform_docs` documentation.


The Toolkit Core API
---------------------------------------------------------

Each instance of the :class:`sgtk.Sgtk` class is associated with a specific set of configuration settings.
This association is automatically resolved as the API instance is created and can be
specified in several ways:

- As a path pointing directly at the desired pipeline configuration
- As a Shotgun entity for which the associated (primary) pipeline configuration is resolved via Shotgun
- As a path to a project folder on disk from which the associated (primary) pipeline configuration is computed.

Factory methods
===============================

The following factory methods are used to create a Toolkit API instance:

.. autofunction:: sgtk_from_path
.. autofunction:: sgtk_from_entity

.. note:: If you are using the :class:`~sgtk.bootstrap.ToolkitManager`, initialization of :class:`sgtk.Sgtk`
          happens behind the scenes. While it is still possible to access a setup managed by the
          :class:`~sgtk.bootstrap.ToolkitManager` via the same methods that you would use to access a
          traditionally set up project, is is usually much easier to let the bootstrap process
          handle the initialization.

Authentication
===============================

Certain API operations require Shotgun data and hence require a way for the API
to establish a connection to Shotgun. The easiest way to handle this is by
making sure that each API instance has an associated authenticated user:

.. autofunction:: set_authenticated_user
.. autofunction:: get_authenticated_user

Sgtk
========================================

.. autoclass:: Sgtk
    :members:
    :exclude-members: pipeline_configuration,
                      log_metric,
                      execute_core_hook,
                      execute_hook,
                      execute_core_hook_method,
                      get_cache_item,
                      set_cache_item


Context
=========================================

.. autoclass:: Context
    :members:
    :exclude-members: tank

Pipeline Configuration Utilities
================================

It is possible to enquiry about the location of various components of the pipeline configuration and
the currently running version of the Toolkit Core.

.. autofunction:: get_core_python_path_for_config
.. autofunction:: get_sgtk_module_path

Executing Tank commands
---------------------------------------------------------

The ``tank`` command offers a variety of system utility commands to handle for example upgrades,
administration and maintenance. These commands are also available to use via the API in order to
make it easy to integrate Toolkit maintenance workflows with other scriped workflows you may have
in your studio. The following commands can be used to manage and execute these functions:

API access methods
=========================================

.. autofunction:: list_commands
.. autofunction:: get_command

SgtkSystemCommand
=========================================

.. autoclass:: SgtkSystemCommand
    :members:


.. _sgtk_hook_docs:

Hooks
---------------------------------------------------------


Hooks are snippets of code that can be customized as part of the configuration of a Toolkit app,
engine or core itself. You can use hooks with the Core API (we call those core hooks) and with
apps and engines. Hooks are a central concept in the configuration of Toolkit. We use hooks whenever
there is a need to expose code and allow it to be customized. Examples
of when this is useful is Disk I/O, launching of applications, DCC-specific logic and permissions control.


Hook
=========================================
.. autoclass:: Hook
    :members:
    :exclude-members: execute, get_publish_paths

get_hook_baseclass
=========================================

.. autofunction:: get_hook_baseclass


Template system
-----------------------------------------

The Toolkit template system is used to handle path and string token manipulations.

Since the Shotgun Toolkit is file system based, Apps will need to resolve file paths whenever
they need to read or write data from disk. Apps are file system structure agnostic - meaning
that they don't know how the file system is organized. The template system handles all this for them.

At the heart of the template system, there is a Templates Configuration File. This file contains
all the important file system locations for a project. A Template looks something like this::

    maya_shot_publish: 'shots/{Shot}/{Step}/pub/{name}.v{version}.ma'

It basically defines a path which contains certain dynamic fields. Each field can be
configured with validation and typing, so you can, for example, define that the ``{version}`` field
in the template above is an integer padded with three zeros (e.g. ``001``, ``012``, ``132``).
Whenever and App needs to write or read something from disk, a template is added to the templates
file to describe that location. Since Apps often are set up to form a pipeline, the output template
of one App (e.g. a publishing app) is often the input template of another app (e.g. a loading app).
This is why all the file system locations are kept in a single file.

The template API lets you jump between a list of field values and paths::

    # get a template object from the API
    >>> template_obj = sgtk.templates["maya_shot_publish"]
    <Sgtk Template maya_asset_project: shots/{Shot}/{Step}/pub/{name}.v{version}.ma>

    # we can use the template object to turn a path into a set of fields...
    >>> path = '/projects/bbb/shots/001_002/comp/pub/main_scene.v003.ma'
    >>> fields = template_obj.get_fields(path)

    {'Shot': '001_002',
     'Step': 'comp',
     'name': 'main_scene',
     'version': 3}

    # alternatively, we can take a fields dictionary and make a path
    >>> template_obj.apply_fields(fields)
    '/projects/bbb/shots/001_002/comp/pub/main_scene.v003.ma'

Note how the above path and template has two different types of fields: The Shot and Step fields are
high-level fields with equivalent objects in Shotgun (a Shot and a Pipeline Step) where the name and
the version fields are very specific to this particular type of template (in this case a publish path.).
If we wanted to describe a publish path for an asset rather than a shot, we would still have a name
and a version field, since this is needed for all publishes, regardless of what type of data it is -
however, we would not have a Shot and a Step field. Instead, we may have an Asset and a Step field,
where the asset field would be associated with an asset in Shotgun.

Template
=========================================

.. autoclass:: Template
    :members:

TemplatePath
=========================================

.. autoclass:: TemplatePath
    :members:

TemplateString
=========================================

.. autoclass:: TemplateString
    :members:
    :exclude-members: get_fields


TemplateKey
=========================================

A template, e.g. ``shots/{Shot}/{Step}/pub/{name}.v{version}.ma`` consists of several dynamic ``{tokens}``.
Each token is represented by a :class:`TemplateKey` object at runtime, where you can access properties and
execute token specific logic.

.. autoclass:: TemplateKey
    :members:

StringKey
=========================================

.. autoclass:: StringKey
    :members:

SequenceKey
=========================================

.. autoclass:: SequenceKey
    :members:

IntegerKey
=========================================

.. autoclass:: IntegerKey
    :members:

TimestampKey
=========================================

.. autoclass:: TimestampKey
    :members:


Configuration file resolution
-----------------------------------------
Each pipeline configuration has configuration files that help Toolkit locate the Python interpreter to use.

.. autofunction:: get_python_interpreter_for_config


Exceptions
------------------------------------------

The following exceptions are raised by the Toolkit Core API classes:

.. autoclass:: TankError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankErrorProjectIsSetup
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankFileDoesNotExistError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankHookMethodDoesNotExistError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankUnreadableFileError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankFileDoesNotExistError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankInvalidInterpreterLocationError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankInvalidCoreLocationError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankNotPipelineConfigurationError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: TankUnreadableFileError
    :show-inheritance:
    :inherited-members:
    :members:


