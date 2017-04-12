# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that provides utilities used by Toolkit's browser integration.
"""

import sgtk

class BrowserIntegration(sgtk.Hook):
    def get_cache_key(self, config_uri, project, entity_type):
        """
        Computes the key used to uniquely identify a row in the cache database for
        the given pipeline configuration uri and entity type. This method can be used
        to change how a specific entity type is cached, should that be desired.

        .. Note:
            Changing the logic in this method will invalidate related cache entries
            that already exist in the cache.

        :param str config_uri: A descriptor uri for the pipeline configuration.
        :param dict project: The project entity.
        :param str entity_type: The entity type.

        :returns: A uniquely-identifiable key.
        :rtype: str
        """
        return "%s@%s" % (config_uri, entity_type)

    def get_site_state_data(self):
        """
        Builds a list of dictionaries matching the kwargs expected by the
        Shotgun Python API's find method. These will be queried at the time
        when a contents state hash is generated during cache population or
        lookup. This hash is then used to verify that the data found in the
        cache is still valid. Customization of this method's logic can be
        used to control what determines whether cached data is valid or not.
        By default, we track the state of the Shotgun site's Software entities
        to determine whether any fields there have changed since the data was
        cached.

        .. Note:
            Changing the logic in this method will invalidate related cache
            entries that already exist in the cache.

        :returns: A list of dictionaries containing kwargs that will be passed
            to the Shotgun Python API's find method.
        :rtype: list
        """
        data_requests = []
        data_requests.append(
            dict(
                entity_type="Software",
                filters=[],
                fields=self.parent.shotgun.schema_field_read("Software").keys(),
            )
        )

        return data_requests

    def process_commands(self, commands, project, entities):
        """
        Allows for pre-processing of the commands that will be returned to the client.
        The default implementation here makes use of this to filter out any commands
        that were not registered by an app. This will remove standard commands that
        are not desirable for display in the SG web app, such as the
        "Reload and Restart" command.

        :param list commands: A list of dictionaries, each containing information
            about a command to be passed up to the client. Each dict will include
            the following keys: name, title, app_name, deny_permissions, and
            supports_multiple_selection.
        :param dict project: The project entity.
        :param list entities: A list of entity dictionaries representing all entities
            that were selected in the web client.

        .. Example:
            dict(
                name="launch_maya",
                title="Maya 2017",
                deny_permissions=[],
                supports_multiple_selection=False,
                app_name="tk-multi-launchapp",
                group="Maya",
                group_default=True,
                engine_name="tk-maya",
            )

        :returns: Processed commands.
        :rtype: list
        """
        return commands



