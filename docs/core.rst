.. _core_api:

.. currentmodule:: sgtk

Core
########################################

The Toolkit Foundation is the part of the Toolkit Core API
that contains lower level components and APIs. These include

- Automatic folder creation
- :class:`Template` system and path resolution APIs
- Execution of Tank Admin commands
- The Toolkit :class:`Context`
- The :class:`Sgtk` Main API class


For apps and engines, see the :ref:`sgtk_platform_docs` documentation.

.. note:: The Toolkit Foundation APIs require that you run them from within
    an initialized toolkit environment. For more information on how to
    set this up, see :ref:`init_and_startup`.


Sgtk
---------------------------------

.. autoclass:: Sgtk
    :members:
    :exclude-members: pipeline_configuration,
                      log_metric,
                      execute_core_hook,
                      execute_hook,
                      execute_core_hook_method,
                      get_cache_item,
                      set_cache_item

Authentication
==============

Certain API operations require Shotgun data and hence require a way for the API
to establish a connection to Shotgun. The easiest way to handle this is by
making sure that each API instance has an associated authenticated user:

.. autofunction:: set_authenticated_user
.. autofunction:: get_authenticated_user

.. note::
    The :class:`Context` serializes the authentication state, so if you are passing a context
    from one process or application to the next, you don't need to utilize the methods above.

Pipeline Configuration Utilities
================================

It is possible to enquiry about the location of various components of the pipeline configuration and
the currently running version of the Toolkit Core.

.. autofunction:: get_core_python_path_for_config
.. autofunction:: get_sgtk_module_path
.. autofunction:: get_python_interpreter_for_config


Context
------------------------------------

.. autoclass:: Context
    :members:
    :exclude-members: tank


Commands
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

Core Hooks
==========

The Toolkit core comes with a set of hooks that can help you tweak how the core behaves. If you
want to take over a certain behavior, copy the hook found inside the core's `hooks <https://github.com/shotgunsoftware/tk-core/tree/master/hooks>`_ folder
and copy it to your configuration's ``core/hooks`` folder.

Here is the list of hooks that be taken over in the Toolkit core.

before_register_publish.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: before_register_publish
.. autoclass:: before_register_publish.BeforeRegisterPublish
    :members:

bootstrap.py
~~~~~~~~~~~~

.. automodule:: bootstrap
.. autoclass:: bootstrap.Bootstrap
    :members:

bundle_init.py
~~~~~~~~~~~~~~

.. automodule:: bundle_init
.. autoclass:: bundle_init.BundleInit
    :members:

cache_location.py
~~~~~~~~~~~~~~~~~

.. automodule:: cache_location
.. autoclass:: cache_location.CacheLocation
    :members:

context_change.py
~~~~~~~~~~~~~~~~~

.. automodule:: context_change
.. autoclass:: context_change.ContextChange
    :members:

engine_init.py
~~~~~~~~~~~~~~

.. automodule:: engine_init
.. autoclass:: engine_init.EngineInit
    :members:

ensure_folder_exists.py
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ensure_folder_exists
.. autoclass:: ensure_folder_exists.EnsureFolderExists
    :members:

get_current_login.py
~~~~~~~~~~~~~~~~~~~~

.. automodule:: get_current_login
.. autoclass:: get_current_login.GetCurrentLogin
    :members:

log_metrics.py
~~~~~~~~~~~~~~

.. automodule:: log_metrics
.. autoclass:: log_metrics.LogMetrics
    :members:
    :exclude-members: execute

pick_environment.py
~~~~~~~~~~~~~~~~~~~

.. automodule:: pick_environment
.. autoclass:: pick_environment.PickEnvironment
    :members:

pipeline_configuration_init.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pipeline_configuration_init
.. autoclass:: pipeline_configuration_init.PipelineConfigurationInit
    :members:

process_folder_creation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: process_folder_creation
.. autoclass:: process_folder_creation.ProcessFolderCreation
    :members:

process_folder_name.py
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: process_folder_name
.. autoclass:: process_folder_name.ProcessFolderName
    :members:

resolve_publish.py
~~~~~~~~~~~~~~~~~~

.. automodule:: resolve_publish
.. autoclass:: resolve_publish.ResolvePublish
    :members:

tank_init.py
~~~~~~~~~~~~

.. automodule:: tank_init
.. autoclass:: tank_init.TankInit
    :members:

Template Hooks
==============

.. automodule:: example_template_hook
.. autoclass:: example_template_hook.ExampleTemplateHook
    :members:

.. currentmodule:: sgtk


Templates
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


