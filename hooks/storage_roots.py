from sgtk import get_hook_baseclass


class StorageRootsResolver(get_hook_baseclass()):
    def resolve_root_path(self, root_name, root_info):
        """
        Executed when a new Toolkit API instance is initialized.

        You can access the Toolkit API instance through ``self.parent``.

        The default implementation does nothing.
        """
        return None
