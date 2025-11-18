.. _environment_variables:

Environment Variables
########################################

A number of different environment variables exist to help control the behavior of the Toolkit Startup.

.. _environment_variables_general:

General
=======

``SHOTGUN_API_CACERTS``
-----------------------
Use this variable to override the default Trusted Root Certification Authorities
Certificate Store bundled with Toolkit.
By default, Toolkit relies on `certifi <https://pypi.org/project/certifi/>`_ as
its Root CA store.

For an example about using ``SHOTGUN_API_CACERTS`` to fix a certificate issue,
see the `SSLHandshakeError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_qa_troubleshooting_qa_sslhandshakeerror_ssl_certificate_verify_failed_html>`_
article.

``SHOTGUN_HOME``
----------------
Overrides the location where Toolkit stores data, which includes bootstrap data as well as bundle cache, cached thumbnails and other temp files.

``SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT``
------------------------------------------
Use this variable to prevent Toolkit from importing the QtWebEngine modules when
importing the PySide2/PySide6 modules.
This variable is useful when a DCC deadlocks while importing the module.

``SGTK_PREFERENCES_LOCATION``
-----------------------------
Allows you to store your configuration file somewhere else on your computer or on your network. See the `documentation here <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_pg_integrations_admin_guides_integrations_admin_guide_html#toolkit-configuration-file>`_.

``TK_BOOTSTRAP_CONFIG_OVERRIDE``
--------------------------------
Low level bypass to set the configuration desciptor URI that the bootstrap API should load up. Useful in complex workflow development scenarios.

``TK_DEBUG``
------------
Controls debug logging.

.. _environment_variables_authentication:

``SGTK_ALLOW_OLD_PYTHON``
-------------------------

When set to ``1``, Toolkit will allow being imported from Python versions that are no longer supported.
Otherwise, when unset (or set to any other value), attempting to import Toolkit from old unsupported Python version will
raise an exception.

This is not recommended and should only be used for testing purposes.

.. important::
    The ability to import the module does not guarantee that Toolkit will work properly on the unsupported Python
    version. In fact, it is very likely that it will not work properly.


Authentication
==============

``SGTK_DEFAULT_AUTH_METHOD``
----------------------------
Specifies which authentication method should be selected if none are selected yet.
Available values are `credentials`, `qt_web_login`, and `app_session_launcher`.

Note: this variable does not override the session cache. If a valid method has
been recorded in the session cache, this method will be prioritized over the
one provided by `SGTK_DEFAULT_AUTH_METHOD`.

``SGTK_AUTH_ALLOW_NO_HTTPS``
----------------------------
Allows the user to bypass the HTTPS requirement for the authentication methods.
This is not recommended and should only be used in combination with legacy ShotGrid local installations.

``SGTK_FORCE_STANDARD_LOGIN_DIALOG``
------------------------------------
Always display the traditional authentication (login and password fields) in the
login window dialog even when the Flow Production Tracking site has other authentication methods
enabled.

``TK_AUTH_PRODUCT``
-------------------
Provide a custom application name when using the "App Session Launcher"
authentication instead of relying on an autodetected name.

``TK_SHOTGRID_DEFAULT_LOGIN``
-----------------------------
Indicates the default Autodesk Identity account to use to pre-fill the login window dialog. This is purely for the convenience of the user and has no other use or side-effects.

``TK_SHOTGRID_SSO_DOMAIN``
--------------------------
When the user's Autodesk Identity account is on an email domain that uses SSO for authentication, setting this variable will allow the bypass of the initial Autodesk Identity window. This saves the user from entering their email twice. The expected format of this variable should be an email domain, like `gmail.com`, `mystudio.com`, `autodesk.com`, etc.. Other than that, this variable has no other use or side-effects.

.. _environment_variables_bundle_cache:

Bundle cache
============

``SHOTGUN_BUNDLE_CACHE_FALLBACK_PATHS``
---------------------------------------
Path that lets a user specify bundle cache fallbacks to go look for a bundle in case it is now found in the bundle cache. This is part of the :ref:`bootstrap_api`. Also see `Flow Production Tracking Integrations Admin guide <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_pg_integrations_admin_guides_integrations_admin_guide_html#managing-updates-via-manual-download>`_.

``SHOTGUN_BUNDLE_CACHE_PATH``
-----------------------------
Overrides the path to the main bundle cache, e.g. the location where the :ref:`Descriptor URI<descriptor>` will download bundles.

``SHOTGUN_DISABLE_APPSTORE_ACCESS``
-----------------------------------
Setting this to ``1`` will disable any Flow Production Tracking Appstore access. No attempts to connect will be carried out. This option can be useful in cases where complex proxy setups is preventing Toolkit to correctly operate.

.. _environment_variables_file_resolving:

File resolving
==============

``SHOTGUN_PATH_<WINDOWS|MAC|LINUX>_<STORAGENAME>``
--------------------------------------------------
Specifies your local storage root on different operating systems. See `Resolving local file links <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_pg_integrations_admin_guides_integrations_admin_guide_html#resolving-local-file-links>`_.

``SHOTGUN_PATH_<WINDOWS|MAC|LINUX>``
------------------------------------
Resolves a ``file://`` URL on different operating systems. See `Resolving file URLS <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_pg_integrations_admin_guides_integrations_admin_guide_html#resolving-file-urls>`_.


Thumbnail display for Flow Production Tracking
======================================================

``SGTK_PROJ_THUMB_OLD``
-----------------------

When specified the old thumbnail cropping behavior will be used. See `Configuring the thumbnail display in Flow Production Tracking <https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_pg_integrations_admin_guides_integrations_admin_guide_html#configuring-the-thumbnail-display-in-shotgrid-desktop>`_
