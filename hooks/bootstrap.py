# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import contextlib

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

    def init(self, shotgun, pipeline_configuration_id, configuration_descriptor, **kwargs):
        """
        This method is invoked when the hook is instantiated.

        It can be used to cache information so it can be reused, for example a
        shotgun connection to external site.

        The ``kwargs`` is there for forward compatibility with future versions of Toolkit.

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

    def download_bundle(self, descriptor, **kwargs):
        """
        This method is invoked during bootstrapping when downloading the core or
        the bundles used by a configuration.

        Your override must download the descriptor's content before the method
        ends or the bundle cache will be left in an inconsistent state.

        The safest way to download a bundle into the bundle cache is by using the
        :meth:`BootstrapHook._open_write_location` method with the `with` statement.

        .. example::
            with self._open_write_location(descriptor) as write_location:
                # Put code that writes the bundle at write_location here.

        Any exception raised in this method will abort the bootstrap process.

        The default implementation will download the descriptor's content from
        its source.

        The ``kwargs`` is there for forward compatibility with future versions of Toolkit.

        :param descriptor: The descriptor that will be downloaded.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """
        descriptor.download_local()

    @contextlib.contextmanager
    def _open_write_location(self, descriptor):
        """
        Allows to write a bundle to the primary bundle cache location.

        This method should be invoked with the ``with`` statement. It yields the
        path where the bundle information needs to be written. If an exception
        is raised inside the ``with`` block, the files will be deleted
        and the bundle cache will be left intact. Be careful to properly copy
        all the files while invoking ``_open_write_location`` or the cache for
        this bundle will be left in an inconsistent state.
        """
        with descriptor._io_descriptor.open_write_location() as write_location:
            yield write_location
