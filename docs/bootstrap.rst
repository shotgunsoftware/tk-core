.. currentmodule:: sgtk.bootstrap

Toolkit Bootstrap and Management
########################################

The ``sgtk.bootstrap`` module contains methods and classes to handle operations around toolkit - managing
configurations, starting up toolkit, deploying and managing configurations etc.


The :class:`ToolkitManager` makes it possible to launch Toolkit without having to install anything
via project setup or similar. The bootstrap process also won't require any configuration values to
be written to Shotgun itself. The following example code can for example run inside maya in order
to launch toolkit's default config for a given Shotgun Asset::

    import sgtk

    # let the user select a site and log in
    sg_auth = sgtk.authentication.ShotgunAuthenticator()
    user = sg_auth.get_user()

    # start up a Toolkit Manager
    mgr = sgtk.bootstrap.ToolkitManager(user)

    # set the base configuration to the default config
    mgr.base_configuration = "sgtk:descriptor:app_store?name=tk-config-default"

    # make sure we grab the latest version
    mgr.resolve_latest_base_configuration = True

    # now start up the maya engine for a given shotgun object
    e = mgr.bootstrap_engine("tk-maya", entity={"type": "Asset", "id": 1234})

Note that the example is primitive and for example purposes only as it will take time to execute
and blocks execution during this period.

The ToolkitManager will handle the setup and initialization of the configuration behind the scenes
and start up a Toolkit session once all the required pieces have been initialized and set up.


.. autoclass:: ToolkitManager
    :members:
    :inherited-members:


Exception Classes
----------------------------------------

.. autoclass:: TankBootstrapError


