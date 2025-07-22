# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import importlib.util

plugin_path = os.path.join(
    os.environ["TK_CORE_REPO_ROOT"], "docs", "examples", "bootstrap_hook.py"
)

spec = importlib.util.spec_from_file_location("bootstrap_unit_test", plugin_path)
BootstrapModule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BootstrapModule)
Bootstrap = BootstrapModule.Bootstrap


class Foo(object):
    pass


# Trick Toolkit's load_plugin method into thinking Bootstrap is actually from this
# module.
Bootstrap.__module__ = Foo.__module__
