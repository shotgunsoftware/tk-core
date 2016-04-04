# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

def swap_core(core_path):
    """Swap the current core with the core located at the supplied path

    Actually just unloads the existing core and ensures an import handler
    exists that points to the supplied core path. When this method completes,
    all core namespaces will be removed from `sys.modules`. The required
    modules will need to be reimported afther this method is called.

    :param core_path: The path to the new core to use upon import.

    """

    # NOTE: this imports the handler from the current core.
    try:
        from tank_vendor.shotgun_deploy.import_handler import CoreImportHandler
    except ImportError:
        # TODO: log a message about not being able to swap the core
        return

    # see if there's already a core import handler in use
    import_handler = None
    for handler in sys.meta_path:
        if isinstance(handler, CoreImportHandler):
            import_handler = handler
            break

    if not import_handler:
        # no import handler yet, create a new one
        import_handler = CoreImportHandler(core_path)

        # add the new import handler to the meta path so that it starts
        # taking over core-related imports
        sys.meta_path.append(import_handler)

    if core_path != import_handler.core_path:
        # the core we want to load differs from the one the import handler
        # is using. we'll set it so that future imports of core namespaces
        # use this new location
        import_handler.set_core_path(core_path)

        # NOTE: once this is called, any imported modules in the core python
        # namespaces will be unloaded. the calling code will need to reimport
        # everything necessary before continuing.
