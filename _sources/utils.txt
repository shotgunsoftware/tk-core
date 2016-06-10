.. currentmodule:: sgtk

Utilities
####################################################

Logging
============================================

.. automodule:: sgtk.log

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

Below are a collection of Shotgun related utility
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



