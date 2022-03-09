.. _environment_variables:

Environment Variables
########################################

A number of different environment variables exist to help control the behavior of the Toolkit Startup.

.. _environment_variables_general:

General
=======

``SHOTGUN_HOME``
----------------
Overrides the location where Toolkit stores data, which includes bootstrap data as well as bundle cache, cached thumbnails and other temp files.

``SGTK_PREFERENCES_LOCATION``
-----------------------------
Allows you to store your configuration file somewhere else on your computer or on your network. See the `documentation here <https://developer.shotgridsoftware.com/8085533c/?title=ShotGrid+Integrations+Admin+Guide#toolkit-configuration-file>`_.

``TK_BOOTSTRAP_CONFIG_OVERRIDE``
--------------------------------
Low level bypass to set the configuration desciptor URI that the bootstrap API should load up. Useful in complex workflow development scenarios.

``TK_DEBUG``
------------
Controls debug logging.

``TK_SHOTGRID_DEFAULT_LOGIN``
-----------------------------
Indicates the default Autodesk Identity account to use to pre-fill the login window dialog. This is purely for the convenience of the user and has no other use or side-effects.

``TK_SHOTGRID_SSO_DOMAIN``
--------------------------
When the user's Autodesk Identity account is on an email domain that uses SSO for authentication, setting this will allow the bypass of the initial Autodesk Identity window. This saves the user from entering their email twice. Has no other use or side-effects.

.. _environment_variables_bundle_cache:

Bundle cache
============

``SHOTGUN_BUNDLE_CACHE_FALLBACK_PATHS``
---------------------------------------
Path that lets a user specify bundle cache fallbacks to go look for a bundle in case it is now found in the bundle cache. This is part of the :ref:`bootstrap_api`. Also see `ShotGrid Integrations Admin guide <https://developer.shotgridsoftware.com/8085533c/?title=ShotGrid+Integrations+Admin+Guide#managing-updates-via-manual-download>`_.

``SHOTGUN_BUNDLE_CACHE_PATH``
-----------------------------
Overrides the path to the main bundle cache, e.g. the location where the :ref:`Descriptor URI<descriptor>` will download bundles.

``SHOTGUN_DISABLE_APPSTORE_ACCESS``
-----------------------------------
Setting this to ``1`` will disable any ShotGrid Appstore access. No attempts to connect will be carried out. This option can be useful in cases where complex proxy setups is preventing Toolkit to correctly operate.

.. _environment_variables_file_resolving:

File resolving
==============

``SHOTGUN_PATH_<WINDOWS|MAC|LINUX>_<STORAGENAME>``
--------------------------------------------------
Specifies your local storage root on different operating systems. See `Resolving local file links <https://developer.shotgridsoftware.com/8085533c/?title=ShotGrid+Integrations+Admin+Guide#resolving-local-file-links>`_.

``SHOTGUN_PATH_<WINDOWS|MAC|LINUX>``
------------------------------------
Resolves a ``file://`` URL on different operating systems. See `Resolving file URLS <https://developer.shotgridsoftware.com/8085533c/?title=ShotGrid+Integrations+Admin+Guide#resolving-file-urls>`_.
