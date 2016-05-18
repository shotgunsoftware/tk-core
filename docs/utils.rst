.. currentmodule:: sgtk

Utilities
####################################################

Logging
============================================

Toolkit uses the standard python logging for its
log management. The :class:`LogManager` class below
acts as an interface that helps make it easy to access
and manage toolkit logging.

All toolkit logging is written into a ``sgtk.*`` logging
namespace. This has been "sealed" so that log messages
from Toolkit do not propagate up to the root logger. This
is to ensure that Toolkit doesn't interfear with other logging
that has been already configured.

Each app, engine and bundle provides access to logging and
these log streams are also collected and organized under the
``sgtk`` logging namespace. This is done by calling
the methods :meth:`sgtk.platform.Engine.logger`, :meth:`sgtk.platform.Application.logger`
or :meth:`sgtk.platform.Framework.logger`.

Each Toolkit :class:`~sgtk.platform.Engine` contains a method :meth:`~sgtk.platform.Engine._emit_log_message`
that can be subclassed if you want to the DCC to display
log messages at runtime.

LogManager
-----------------------------------

.. autoclass:: LogManager
    :members:


File System Utilities
============================================

Below is a collection of file system related
convenience methods that make it easy to manage
and create files and folders on disk in a standard
fashion.

.. note:: These methods are not configurable or overridable
          by hooks. If you are developing apps or engines, we
          recommend using :meth:`~sgtk.platform.Application.ensure_folder_exists`
          as this method calls out to a customizable hook implementation.

.. currentmodule:: sgtk.util.filesystem


sgtk.util.filesystem
-----------------------------------

.. autofunction:: with_cleared_umask
.. autofunction:: touch_file(path, permissions=0666)
.. autofunction:: ensure_folder_exists(path, permissions=0775, create_placeholder_file=False)
.. autofunction:: copy_file(src, dst, permissions=0555)
.. autofunction:: safe_delete_file
.. autofunction:: copy_folder(src, dst, folder_permissions=0775, skip_list=None)
.. autofunction:: move_folder(src, dst, folder_permissions=0775)
.. autofunction:: create_valid_filename

ShotgunPath
-----------------------------------

.. autoclass:: sgtk.util.ShotgunPath
    :members:

LocalFileStorageManager
-----------------------------------

.. autoclass:: sgtk.util.LocalFileStorageManager
    :members:

Shotgun Related
=============================

Below are a collection of shotgun related utility
and convenience methods:

.. currentmodule:: sgtk.util

.. autofunction:: register_publish(tk, context, path, name, version_number, **kwargs)
.. autofunction:: find_publish(tk, list_of_paths, f ilters=None, fields=None)
.. autofunction:: download_url(sg, url, location)
.. autofunction:: create_event_log_entry(tk, context, event_type, description, metadata=None)
.. autofunction:: get_entity_type_display_name
.. autofunction:: get_published_file_entity_type


Miscellaneous
=============================

.. autofunction:: append_path_to_env_var
.. autofunction:: prepend_path_to_env_var
.. autofunction:: get_current_user



