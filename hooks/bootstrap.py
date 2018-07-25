# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk import get_hook_baseclass


class BootstrapHook(get_hook_baseclass()):
    """
    The bootstrap hook can be added to a configuration's core hooks folder
    (``config/core/hooks``) in order to override some of the functionality of
    the ToolkitManager's bootstrapping process.

    The hook will be instantiated only after a configuration has been selected
    by the ``ToolkitManager``. Therefore, the ``download_bundle`` method
    will not be invoked to download a configuration. However, the Toolkit Core,
    applications, frameworks and engines will be downloaded through the hook.
    """

    def init(self, shotgun, pipeline_configuration_id, configuration_descriptor):
        """
        This method is invoked when the hook is instantiated.

        It can be used to cache information so it can be reused.

        :param shotgun: Connection to the Shotgun site.
        :type shotgun: :class:`shotgun_api3.Shotgun`

        :param pipeline_configuration_id: Id of the pipeline configuration we're bootstrapping into.
            If None, the ToolkitManager is bootstrapping into the base configuration.
        :type pipeline_configuration_id: int

        :param configuration_descriptor: Configuration the manager is bootstrapping into.
        :type configuration_descriptor: :class:`sgtk.descriptor.ConfigDescriptor`
        """
        self.shotgun = shotgun
        self.pipeline_configuration_id = pipeline_configuration_id
        self.configuration_descriptor = configuration_descriptor

    def download_bundle(self, descriptor):
        """
        This method is invoked during bootstrapping when downloading the core or
        the bundles used by a configuration.

        Your override must download the descriptor's content before the method
        ends or the bundle cache will be left in an inconsistent state.

        The safest way to download a bundle into the bundle cache is by using the
        :meth:`sgtk.descriptor.Descriptor.open_write_location` context manager.

        Any exception raised in this method will abort the bootstrap process.

        The default implementation will download the descriptor's content from
        its source.

        :param descriptor: The descriptor that will be downloaded.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """
        descriptor.download_local()
