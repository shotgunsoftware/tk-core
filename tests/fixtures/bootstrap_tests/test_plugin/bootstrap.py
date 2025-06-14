# *****************************************************************************
# Copyright (c) 2018 Autodesk, Inc.
# All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************

import importlib
import os
import sys
import time

import sgtk

ENGINE_NAME = "test_engine"


def bootstrap_plugin():
    """
    Bootstrap this plugin.
    """
    # measure the time it takes to start up
    time_before = time.time()

    # Initialize logging to disk
    sgtk.LogManager().initialize_base_file_handler(ENGINE_NAME)

    # Log to stderr if TK_DEBUG is enabled.
    if sgtk.LogManager().global_debug:
        sgtk.LogManager().initialize_custom_handler()

    logger = sgtk.LogManager.get_logger("bootstrap")
    logger.debug("Bootstrapping %s..." % ENGINE_NAME)

    # Figure out our location
    plugin_root_dir = os.path.abspath(os.path.dirname(__file__))
    plugin_python_path = os.path.join(plugin_root_dir, "python")

    # As a baked plugin we do have manifest.py we can use to bootstrap.

    # Instead of adding an extra path in the PYTHONPATH to be able to load the
    # manifest module and clean up the PYTHONPATH up after the import, we use
    # `importlib` utilities to load the manifest module.
    sys.path.insert(0, plugin_python_path)
    sgtk_plugin_test_plugin = importlib.import_module("sgtk_plugin_test_plugin")

    # This module is built with the plugin and contains the manifest.py.
    manifest = sgtk_plugin_test_plugin.manifest

    # start up toolkit via the manager - we should be authenticated already.
    manager = sgtk.bootstrap.ToolkitManager()
    manifest.initialize_manager(manager, plugin_root_dir)

    # This plugin is fully baked and cannot be overridden
    # via a Shotgun Pipeline Configuration.
    # Note: Individual apps can however be overridden since
    #       the execute in external processes.
    manager.do_shotgun_config_lookup = False

    # start up in site mode.
    engine = manager.bootstrap_engine(ENGINE_NAME, entity=None)
    logger.debug("%s started." % engine.name)

    time_spent = time.time() - time_before
    engine.log_info("Toolkit integration launched in %ss" % time_spent)


if __name__ == "__main__":
    bootstrap_plugin()
