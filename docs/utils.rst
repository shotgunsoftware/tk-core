.. currentmodule:: sgtk

Utilities
####################################################

.. _logging:

Logging
============================================

.. automodule:: sgtk.log

LogManager
-----------------------------------

.. autoclass:: LogManager
    :members:


.. _centralizing_settings:

Centralizing your settings
==========================

Instead of customizing your proxy settings on each of your project, it is possible to configure them once in a file
and have your projects inherit these values, unless the project overrides itself the setting
inside ``shotgun.yml``.

Here's an example:

    .. code-block:: ini

        # Login related settings
        #
        [Login]

        # If specified, the username text input on the login screen will be populated
        # with this value when logging into Toolkit for the very first time.
        # Defaults to the user's OS login. Environment variables are actually resolved for
        # all values in this file, which allows greater flexibility when sharing this configuration
        # file with multiple users.
        #
        default_login=$USERNAME

        # If specified, the site text input on the login screen will be populated with
        # this value when logging into Toolkit the very first time.
        # Defaults to https://mystudio.shotgunstudio.com.
        #
        default_site=https://your-site-here.shotgunstudio.com

        # If specified, the Toolkit will use these proxy settings to connect to
        # the Shotgun site and the Toolkit App Store. The proxy string should be of the
        # forms 123.123.123.123, 123.123.123.123:8888 or
        # username:pass@123.123.123.123:8888.
        # Empty by default.
        #
        http_proxy=123.234.345.456:8888

        # If specified, the Shotgun API will use these proxy settings to connect
        # to the Toolkit App Store. The proxy string format is the same as http_proxy.
        # If the setting is present in the file but not set, then no proxy will be used
        # to connect to the Toolkit App Store, regardless of the value of the http_proxy
        # setting.
        # Empty by default.
        #
        app_store_http_proxy=123.234.345.456:8888

This file can be configured through multiple means and Toolkit will try to resolve the file in the
following order:

1. The ``SGTK_PREFERENCES_LOCATION`` environment variable,
2. The ``SGTK_DESKTOP_CONFIG_LOCATION`` environment variable, for compatibility with the Shotgun Desktop. (deprecated)
3. Inside the Shotgun Toolkit preferences file
4. Inside the Shotgun Desktop preferences file, for compatibility with the Shotgun Desktop. (deprecated)

.. note::
    The Shotgun Toolkit preferences file is located at:

    - Windows: ``%APPDATA%\Shotgun\Preferences\toolkit.ini``
    - macOS: ``~/Library/Preferences/Shotgun/toolkit.ini``
    - Linux: ``~/.shotgun/preferences/toolkit.ini``

    The Shotgun Desktop preferences file is located at:

    - Windows: ``%APPDATA%\Shotgun\desktop\config\config.ini``
    - macOS: ``~/Library/Caches/Shotgun/desktop/config/config.ini``
    - Linux: ``~/shotgun/desktop/config/config.ini``

    Note that the ``SHOTGUN_HOME`` environment variable can impact the location
    of the Shotgun Toolkit preferences file.

.. note::
    When the http proxy is not specified in this file, the Shotgun Toolkit will try to retrieve
    the operating system http proxy.

    First, the environment will be scanned for variables named ``http_proxy``, in case insensitive way.
    If both lowercase and uppercase environment variables exist (and disagree), lowercase will be preferred.

    When such environment variables cannot be found:

    - for Mac OS X, proxy information will be looked for from Mac OS X System Configuration,
    - for Windows, proxy information will be looked for from Windows Systems Registry.

    There is a restriction in these latter cases: the use of proxies which require
    authentication (username and password) is not supported.

    Internally, the Shotgun Toolkit uses Python function ``urllib.getproxies()`` to retrieve
    the operating system http proxy. More information about this function can be found here:

        https://docs.python.org/2/library/urllib.html#urllib.getproxies

You can access those values programmatically.

.. autoclass:: sgtk.util.UserSettings
    :members:
    :exclude-members: __new__


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
.. autofunction:: compute_folder_size
.. autofunction:: touch_file(path, permissions=0666)
.. autofunction:: ensure_folder_exists(path, permissions=0775, create_placeholder_file=False)
.. autofunction:: copy_file(src, dst, permissions=0666)
.. autofunction:: safe_delete_file
.. autofunction:: safe_delete_folder
.. autofunction:: copy_folder(src, dst, folder_permissions=0775, skip_list=None)
.. autofunction:: move_folder(src, dst, folder_permissions=0775)
.. autofunction:: backup_folder
.. autofunction:: create_valid_filename
.. autofunction:: get_unused_path

.. currentmodule:: sgtk.util.json


sgtk.util.json
-----------------------------------

.. autofunction:: load
.. autofunction:: loads


.. currentmodule:: sgtk.util.pickle


sgtk.util.pickle
-----------------------------------

Toolkit's ``pickle`` module isn't a drop-in replacement for Python's, but a wrapper around Python's :mod:`pickle` module so collections and scalar types can be exchanged freely between Python 2 and Python 3 processes without having to worry about the subtle pickle serialization differences between the two.

If you wish to serialize your own custom classes to be exchanged between Python 2 and Python 3, you will need to sanitize data unpickled with Python 2 that was pickled with Python 3 and vice-versa. Otheriwse, your data will contain unexpected ``bytes`` or ``unicode`` objects instead of utf-8 encoded ``str`` instances.

.. note::
    In the ``load``/``loads`` methods, Python 3's ``bytes`` is always decoded back to a utf-8 encoded ``str``. If you need to store arbitrary binary data, consider saving it as a base64 string instead.

.. autofunction:: dump
.. autofunction:: dumps
.. autofunction:: load
.. autofunction:: loads


ShotgunPath
-----------------------------------

.. autoclass:: sgtk.util.ShotgunPath
    :members:

LocalFileStorageManager
-----------------------------------

.. autoclass:: sgtk.util.LocalFileStorageManager
    :members:


.. currentmodule:: sgtk.util

OS detection
=============================

Below are a collection of convenience methods to detect which operating system is in use:

.. autofunction:: is_linux
.. autofunction:: is_windows
.. autofunction:: is_macos


Shotgun Related
=============================

Below are a collection of Shotgun related utility
and convenience methods:

.. currentmodule:: sgtk.util

.. autofunction:: register_publish(tk, context, path, name, version_number, **kwargs)

.. autofunction:: resolve_publish_path(tk, sg_publish_data)

.. autofunction:: find_publish(tk, list_of_paths, f ilters=None, fields=None)
.. autofunction:: create_event_log_entry(tk, context, event_type, description, metadata=None)
.. autofunction:: get_entity_type_display_name
.. autofunction:: get_published_file_entity_type
.. autofunction:: get_sg_entity_name_field

File Download Related
=============================

.. autofunction:: download_url(sg, url, location)
.. currentmodule:: sgtk.util.shotgun
.. autofunction:: download_and_unpack_attachment(sg, attachment_id, target, retries=5, auto_detect_bundle=False)
.. autofunction:: download_and_unpack_url(sg, url, target, retries=5, auto_detect_bundle=False)


Version Comparison Related
=============================

.. currentmodule:: sgtk.util

.. autofunction:: is_version_older
.. autofunction:: is_version_older_or_equal
.. autofunction:: is_version_newer
.. autofunction:: is_version_newer_or_equal

Miscellaneous
=============================

.. currentmodule:: sgtk.util
.. autofunction:: append_path_to_env_var
.. autofunction:: prepend_path_to_env_var
.. autofunction:: get_current_user


Exceptions
================================================

.. autoclass:: sgtk.util.EnvironmentVariableFileLookupError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: sgtk.util.ShotgunPublishError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: sgtk.util.PublishResolveError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: sgtk.util.PublishPathNotDefinedError
    :show-inheritance:
    :inherited-members:
    :members:

.. autoclass:: sgtk.util.PublishPathNotSupported
    :show-inheritance:
    :inherited-members:
    :members:
