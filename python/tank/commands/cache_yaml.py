# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import fnmatch
import json
import logging
import os

from ..errors import TankError
from ..util import yaml_cache
from .action_base import Action


class CacheYamlAction(Action):
    """
    Action that ensures that crawls a config, caching all YAML data found
    to disk as data-only JSON.
    """

    def __init__(self):
        Action.__init__(
            self,
            "cache_yaml",
            Action.TK_INSTANCE,
            "Populates a cache of all YAML data found in the config.",
            "Admin",
        )

        # this method can be executed via the API
        self.supports_api = True

    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor.
        Called when someone runs a tank command through the core API.

        This command takes no parameters, so an empty dictionary
        should be passed. The parameters argument is there because
        we are deriving from the Action base class which requires
        this parameter to be present.

        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        return self._run(log)

    def run_interactive(self, log, args):
        """
        Tank command accessor

        :param log: std python logger
        :param args: command line args
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        return self._run(log)

    def _run(self, log: logging.Logger) -> None:
        """
        Actual execution payload
        """
        log.info(
            "This command will traverse the entire configuration and build a "
            "cache of all YAML data found."
        )

        root_dir = self.tk.pipeline_configuration.get_path()

        matches = []
        for root, dir_names, file_names in os.walk(root_dir):
            for file_name in fnmatch.filter(file_names, "*.yml"):
                matches.append(os.path.join(root, file_name))
        for path in matches:
            log.debug("Caching %s..." % path)
            yaml_cache.g_yaml_cache.get(path)

        items = yaml_cache.g_yaml_cache.get_cached_items()
        cache_path = self.tk.pipeline_configuration.get_yaml_cache_location()
        log.debug(f"Writing cache to {cache_path}")

        # The cache is written as data-only JSON rather than as a pickle.
        # Pickle executes arbitrary code on load, which is a code-execution
        # risk because this file lives inside a pipeline configuration that may
        # be stored on a shared location. See SG-46278 / PSIRT-3972 (CWE-502).
        #
        # Any item whose YAML payload would not survive a JSON round-trip
        # unchanged (for example it contains a datetime or bytes value, or a
        # non-string mapping key) is skipped. Such an item is simply read live
        # from disk on next access, so behaviour is unchanged - the cache is
        # only an optimization.
        serializable_items = []
        skipped = 0
        for item in items:
            item_dict = item.to_dict()
            if not yaml_cache.is_round_trip_safe(item_dict["data"]):
                skipped += 1
                log.debug(
                    "Skipping yaml cache item whose data is not JSON "
                    f"round-trip safe: {item_dict['path']}"
                )
                continue
            serializable_items.append(item_dict)

        try:
            with open(cache_path, "w", encoding="utf-8") as fh:
                json.dump(serializable_items, fh)
        except Exception as e:
            raise TankError(f"Unable to write yaml cache data: {e}")

        if skipped:
            log.info(
                f"{skipped} yaml file(s) were not cached because their data is "
                "not JSON-serializable; they will be read directly when needed."
            )

        log.info("")
        log.info("Cache yaml completed!")
