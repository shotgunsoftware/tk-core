import os
from sgtk import hook
from sgtk import LogManager

log = LogManager.get_logger(__name__)


# FIXME: This class has a terrible name, we need to rename it.

class BundleDownloader(object):
    """docstring for BundleDownloader"""
    def __init__(self, connection, pipeline_config_id, descriptor):
        super(BundleDownloader, self).__init__()

        # First put our base hook implementation into the array.
        base_class_path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__), # ./python/tank/bootstrap
                "..",                      # ./python/tank
                "..",                      # ./python
                "..",                      # ./
                "hooks",                   # ./hooks
                "bootstrap.py"             # ./hooks/bootstrap.py
            )
        )
        hook_inheritance_chain = [base_class_path]
        # Then, check if there is a config-level override.
        hook_path = os.path.join(
            descriptor.get_config_folder(), "core", "hooks", "bootstrap.py"
        )
        if os.path.isfile(hook_path):
            hook_inheritance_chain.append(hook_path)

        self._hook_instance = hook.create_hook_instance(
            hook_inheritance_chain, parent=None
        )
        self._hook_instance.init(
            connection, pipeline_config_id, descriptor
        )

    def download_bundle(self, descriptor):
        """
        Downloads a bundle referenced by a descriptor. If the populate_bundle_cache_entry
        method is implemented on the bootstrap hook, it will be invoked.
        """
        if self._hook_instance.can_cache_bundle(descriptor):
            with descriptor._io_descriptor.open_write_location() as temporary_folder:
                self._hook_instance.populate_bundle_cache_entry(temporary_folder, descriptor)
        else:
            descriptor.download_local()
