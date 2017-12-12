# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import inspect

from .import_handler import CoreImportHandler

from ..descriptor.descriptor_installed_config import InstalledConfigDescriptor
from ..pipelineconfig_utils import get_core_path_for_config

from ..log import LogManager

log = LogManager.get_logger(__name__)


class Configuration(object):
    """
    An abstraction representation around a toolkit configuration.
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_DIFFERENT, LOCAL_CFG_INVALID) = range(4)

    def __init__(self, path, descriptor):
        """
        :param path: :class:`~sgtk.util.ShotgunPath` object describing the path to this configuration
        :param descriptor: :class:`~sgtk.descriptor.Descriptor` object associated with this
            configuration.
        """
        self._path = path
        self._descriptor = descriptor
        self._core_descriptor = None

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_DIFFERENT, or LOCAL_CFG_INVALID
        """
        raise NotImplementedError

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.
        """
        raise NotImplementedError

    @property
    def descriptor(self):
        """
        Gets the descriptor object associated with the configuration.
        :rtype: :class:`~sgtk.descriptor.Descriptor`
        """
        return self._descriptor

    @property
    def path(self):
        """
        Gets the path to the pipeline configuration on disk.
        :rtype: :class:`~sgtk.util.ShotgunPath`
        """
        return self._path

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
        """
        path = self._path.current_os
        # FIXME: The _get_core_descriptor method needs to be implemented in
        # InstalledConfiguration and BakedConfiguration.

        is_lean_config = (
            self._descriptor.get_associated_core_feature_info(
                "bootstrap.lean_config.version", 0
            ) > 0
        )

        if isinstance(self._descriptor, InstalledConfigDescriptor):
            core_install_folder = get_core_path_for_config(path)
        else:
            core_install_folder = path
            if is_lean_config:
                core_path = os.path.join(
                    self._get_core_descriptor().get_path(),
                    "python"
                )
            else:
                core_path = os.path.join(core_install_folder, "install", "core", "python")

        # swap the core out
        CoreImportHandler.swap_core(core_path)
        os.environ["TANK_CURRENT_PC"] = path

        # perform a local import here to make sure we are getting
        # the newly swapped in core code
        from .. import api
        from .. import pipelineconfig

        log.debug("Core swapped, authenticated user will be set.")

        self._set_authenticated_user(sg_user, is_lean_config, core_install_folder)

        log.debug("Executing tank_from_path('%s')" % path)

        # now bypass some of the very extensive validation going on
        # by creating a pipeline configuration object directly
        # and pass that into the factory method.

        # Previous versions of the PipelineConfiguration API didn't support having a descriptor
        # passed in, so we'll have to be backwards compatible with these. If the pipeline
        # configuration does support the get_configuration_descriptor method however, we can
        # pass the descriptor in.
        if hasattr(pipelineconfig.PipelineConfiguration, "get_configuration_descriptor"):
            pc = pipelineconfig.PipelineConfiguration(path, self.descriptor)
        else:
            pc = pipelineconfig.PipelineConfiguration(path)

        tk = api.tank_from_path(pc)

        log.debug("Bootstrapped into tk instance %r (%r)" % (tk, tk.pipeline_configuration))
        log.debug("Core API code located here: %s" % inspect.getfile(tk.__class__))

        return tk

    def _set_authenticated_user(self, user, is_lean_config, core_install_folder):
        """
        Sets the authenticated user.

        If the project that is being bootstrapped into is configured to use a script user inside
        shotgun.yml, the passed in user will be ignored.

        :param user: User that was used for bootstrapping.
        """

        # perform a local import here to make sure we are getting
        # the newly swapped in core code
        from .. import api

        # It's possible we're bootstrapping into a core that doesn't support the authentication
        # module, so test for the existence of the set_authenticated_user method.
        if not hasattr(api, "set_authenticated_user"):
            log.debug("Using pre-0.16 core, no authenticated user will be set.")
            return

        log.debug("Project core supports the authentication module.")

        # Very important, use backwards compatible imports. These imports go back
        # to the original v0.16 release.
        from tank_vendor.shotgun_authentication import ShotgunAuthenticator
        from ..util import CoreDefaultsManager

        # If the core supports lean config's, it means the core can be run from
        # outside config and shotgun.yml can't be found relative to it, so we'll
        # pass the pipeline configuration root location to the factory, which will
        # figure where shotgun.yml should be located.
        if is_lean_config:
            defaults_manager = CoreDefaultsManager(core_install_folder=core_install_folder)
        else:
            defaults_manager = CoreDefaultsManager()

        # Check to see if there is a user associated with the current project.
        default_user = ShotgunAuthenticator(defaults_manager).get_default_user()

        # Assume we'll use the same user as was used for bootstrapping to authenticate.
        authenticated_user = user
        # If we have a user...
        if default_user:
            # ... and it doesn't have a login
            if not default_user.login:
                log.debug("Script user '%r' found for this project.", default_user)
                # it means we're dealing with a script user and we'll use that, so override
                # the authenticated user.
                authenticated_user = default_user
            else:
                # We found a user, but we'll ignore it.
                log.debug(
                    "'%r' found for this project, "
                    "but ignoring it in favor of bootstrap's user.", default_user
                )
        else:
            # If there is no script user, always use the user passed in instead of the one
            # detected by the CoreDefaultsManager. This is because how core detects users has
            # changed over time and sometimes this causes confusion and we might end up with no
            # users returned by CoreDefaultsManager. By always using the user used to bootstrap,
            # we ensure we will remain logged with the same credentials.
            log.debug("No user was found using the core associated with the project.")

        log.debug("'%r' will be used.", authenticated_user)

        api.set_authenticated_user(authenticated_user)

        return authenticated_user
