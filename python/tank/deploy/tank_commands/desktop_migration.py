# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import textwrap

from .action_base import Action
from . import console_utils
from ...platform import constants

_MESSAGE = ("This will migrate the Shotgun Desktop configuration away from the 'Template "
            "Project'. Before running this, make sure all your users have installed version 1.2.0 or "
            "greater of the Shotgun Desktop or that they are running version 1.2.0 or greater of the Startup framework. "
            "You can see which versions you are running in the Shotgun Desktop's About Box.")


class DesktopMigration(Action):
    """
    Action that migrates the Shotgun Desktop away from the Template Project.
    """
    def __init__(self):
        """
        Constructor
        """
        Action.__init__(self,
                        "migrate_desktop",
                        Action.TK_INSTANCE,
                        "Migrates Shotgun Desktop away from the Template Project.",
                        "Admin")

    def run_interactive(self, log, args):
        """
        Tank command accessor (tank migrate_desktop)
        Retrieves the pipeline configuration from Shotgun and unassigns it from the Template Project.
        """

        log.info("Retrieving pipeline configuration from Shotgun...")

        pc = self.tk.pipeline_configuration

        # Fetch the project id from the actual pipeline configuration.
        sg_pc = self.tk.shotgun.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            [["id", "is", pc.get_shotgun_id()]],
            ["project.Project.name"]
        )

        # If the pipeline configuration doesn't exist anymore, abort.
        if not sg_pc:
            log.error("Pipeline configuration '%d' doesn't seem to exist anymore." % pc.get_shotgun_id())
            return

        # If a pipeline configuration is not assigned to the Template Project, abort.
        project_name = sg_pc["project.Project.name"]
        if project_name and project_name != "Template Project":
            log.error(
                "Migration is possible only from the project named \"Template Project\". This "
                "configuration is for project '%s'" % project_name)
            return

        # Make sure the user really wants to go forward with the migration.
        do_migration = console_utils.ask_yn_question(
            "\n".join(textwrap.wrap(_MESSAGE, width=68)) + "\nDo you want to continue?"
        )

        if not do_migration:
            return

        if project_name:
            # Allright, we can now update the pipeline configuration to make it projectless.
            self.tk.shotgun.update(
                constants.PIPELINE_CONFIGURATION_ENTITY,
                pc.get_shotgun_id(),
                {"project": None}
            )
            log.debug("Pipeline Configuration updated in Shotgun.")
        else:
            log.warning("Pipeline configuration isn't assigned to a project in Shotgun.")

        # Upgrade site configuration on disk.
        if not pc.is_site_configuration():
            pc.convert_to_site_config()
            log.debug("Site Configuration updated.")
        else:
            log.warning("Site configuration is already updated.")

        log.info("The migration completed successfully.")
