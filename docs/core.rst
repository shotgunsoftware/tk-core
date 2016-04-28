.. currentmodule:: sgtk

Toolkit Core API
########################################

Welcome to the Core API documentation! This part of the documentation covers the part of the
API that deals with the core part of Sgtk, for example file system manipulation, how to
identify the key sections in a path and how to access Shotgun.

Creating an API
=========================================



.. autofunction:: sgtk_from_path

.. autofunction:: sgtk_from_entity


Sgtk API
=========================================


.. autofunction:: set_authenticated_user
.. autofunction:: get_authenticated_user

.. autoclass:: Sgtk
    :members:

.. autoclass:: Tank
    :members:
    :exclude-members: pipeline_configuration

Context
=========================================

.. autoclass:: Context
    :members:


.. autoclass:: TemplatePath
    :inherited-members:
    :members:

.. autoclass:: TemplateString
    :inherited-members:
    :members:



Errors
=========================================


.. autoclass:: TankError

.. autoclass:: TankUnreadableFileError

.. autoclass:: TankFileDoesNotExistError

.. autoclass:: TankNoDefaultValueError

.. autoclass:: TankErrorProjectIsSetup

.. autoclass:: TankHookMethodDoesNotExistError