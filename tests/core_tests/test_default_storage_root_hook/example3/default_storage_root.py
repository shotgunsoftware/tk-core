import os
import sgtk

from tank import Hook
from tank.util.storage_roots import StorageRoots

log = sgtk.LogManager.get_logger(__name__)


class DefaultStorageRoot(Hook):
    def execute(self, storage_roots, project_id=None, metadata=None):
        """
        Custom implementation sets default root to project-specific storage root path stored
        in a custom project field on Flow Production Tracking site called "projects root"
        """
        if not project_id:
            return

        # query project-specific storage root's name
        sg_data = self.parent.shotgun.find_one(
            "Project",
            [["id", "is", project_id]],
            ["sg_projects_root"],
        )

        # check if custom field was set and filled
        if not sg_data or not sg_data.get("sg_projects_root"):
            log.info("No project root for project configured, using global storage root.")
            return

        # Stores the Windows drive for the project, e.g "P:"
        drive_root = sg_data["sg_projects_root"]
        # check if local storage exists on SG site
        local_storage = self.parent.shotgun.find(
            "LocalStorage", [['windows_path', 'is', drive_root]], ['code']
        )

        if not local_storage:
            log.warning(
                "The file storage %s for project %d is not defined for this operating system."
                % (drive_root, project_id)
            )
            return
        # Check if we have folder creation metadata
        if metadata:
            # Override data associated with the directory to use the new storage root.
            metadata.update({"root_name": local_storage[0]['code']})

        # Update the default configuration root to map to the correct SG LocalStorage in the
        # StorageRoots object.
        log.info('Overriding project root to LocalStorage %s' % local_storage)
        storage_roots.update_root(
            'primary_mapped',
            {
                "default": True,
                "shotgun_storage_id": local_storage[0]['id'],
                "windows_path": drive_root,
            }
        )

        # Write the updated metadata into the '.../config/core/roots.yml' file in the localised
        # configuration. This should ensure that any StorageRoots.from_config(...) calls return
        # correctly.
        config_folder = os.path.join(self.parent.pipeline_configuration.get_path(), 'config')
        StorageRoots.write(self.parent.shotgun, config_folder, storage_roots)
