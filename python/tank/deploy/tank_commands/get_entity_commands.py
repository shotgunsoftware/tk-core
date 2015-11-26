# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from .action_base import Action
from ...errors import TankError


class GetEntityCommandsAction(Action):
    """
    Gets the commands that can be launched on certain entities for another
    pipeline configuration.

    This is done by calling the tank command on the other pipeline
    configuration and asking it for its cached entity commands (or asks it to
    update its cache beforehand if needed).

    It is used like this:
    >>> import tank
    # create our command object
    >>> cmd = tank.get_command("get_entity_commands")
    # get the commands for tasks
    >>> tasks = [("Task", 1234), ("Task", 1235)]
    >>> commands_by_task = cmd.execute({"pc_path": "/my/pc/path",
    >>>                                 "entities": tasks})
    # extract the commands of a specific task
    >>> commands = commands_by_task[tasks[0]]
    """
    def __init__(self):
        Action.__init__(self,
                        "get_entity_commands",
                        Action.GLOBAL,
                        ("Gets the available commands that can be executed "
                         "for specified entities from another pipeline "
                         "configuration"),
                        "API")

        # no tank command support for this one because it returns an object
        self.supports_tank_command = False

        # this method can be executed via the API
        self.supports_api = True

        self.parameters = {
            "pc_path": {
                "description": "Path to the pipeline configuration associated "
                               "with the entities.",
                "type":        "str"
            },

            "entities": {
                "description": """List of entities to fetch the actions for.
                                  Every entity should be a tuple with the
                                  following format:
                                    (entity_type, entity_id)""",
                "type":        "list"
            },

            "return_value": {
                "description": """Dictionary of the commands by entity, with
                                  the (entity_type, entity_id) tuple used as a
                                  key. Each value is a list of commands. A
                                  command is a dictionary with the following
                                  format:
                                    {
                                      "name":  command to execute
                                      "title": title to display for the command
                                      "icon":  path to the icon of this command
                                    }""",
                "type":        "dict"
            }
        }

    def run_interactive(self, log, args):
        """
        Tank command accessor

        :param log: std python logger
        :param args: command line args
        """
        raise TankError("This Action does not support command line access")

    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor.
        Called when someone runs a tank command through the core API.

        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        pc_path = parameters["pc_path"]
        entities = parameters["entities"]

        commands_per_entity = {}

        for entity in entities:
            commands_per_entity[entity] = {
                "name":  "TODO",
                "title": "work in progress",
                "icon":  ""
            }

        return commands_per_entity
