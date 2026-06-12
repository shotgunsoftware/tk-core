# -
# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
#

from __future__ import annotations  # needed for Houdini support

from abc import ABC, abstractmethod


class FlowHost(ABC):
    """Abstract base class defining a required interface for DCC/engine
    integration with Flow asset management in toolkit.
    """

    #: The schema name associated with workfiles created for this host
    WORKFILE_TYPE = ""
    #: File extensions associated with host DCC (e.g. "ma" for Maya)
    #: Must have at least one value in a subclass implementation
    FILE_TYPES: list[str] = []
    #: Host specific mime type mappings
    #: key = file extension from FILE_TYPES, value = mime type
    MIME_TYPES: dict[str, str] = {}

    def __init__(self, context):
        """Base class initialization.

        Args:
            context: Sgtk context object to be passed in from engine.
        """
        # Store sgtk context
        self.context = context

    @abstractmethod
    def current_file(self) -> str:
        """Return current open file path in dcc."""
        raise NotImplementedError()

    @abstractmethod
    def new_scene(self, force: bool = True) -> bool:
        """Open new scene in the host application.

        Args:
            force: If true, force action even if there are unsaved changes.

        Returns:
            True if new scene is opened, False on error or if operation is cancelled.
        """
        raise NotImplementedError()

    @abstractmethod
    def open_file(self, filepath: str, force: bool = True) -> bool:
        """Open the specified file in the host application.

        Args:
            file_path: Absolute path to the local file to open.
            force: If true, force action even if there are unsaved changes.

        Returns:
            True if file is opened, False on error or if operation is cancelled.
        """
        raise NotImplementedError()

    def save_file(self, file_path: str):
        """Save the current scene to the specified file path.

        This operation may not be applicable to all hosts.

        Args:
            file_path: Absolute local path to save file.
        """
        pass

    def export(self, file_path: str):
        """Export current scene to file path specified and file type
        designated by file extension.

        This operation may not be applicable to all hosts.

        Args:
            file_path: Absolute local path to export file.
        """
        pass

    @abstractmethod
    def dialog(
        self,
        title: str,
        msg: str,
        buttons: list[str] | None = None,
        default: int = 0,
        cancel: int | None = None,
        no_ui_option: int | None = None,
    ) -> int:
        """Pop up a dialog in the host application.

        Args:
            title: Title of dialog window.
            msg: Message to be displayed.
            buttons: List of strings denoting buttons to be added to dialog.
            default: Index of default button.
            cancel: Index of cancel button.
            no_ui_option: If host is running without a UI,
                          this option will automatically be returned.
                          If None, use default value.

        Returns:
            The index of the button selected by user.
            Value of -1 indicates a dismissed dialog.
        """
        raise NotImplementedError()

    @abstractmethod
    def file_dialog(
        self,
        title: str,
        starting_dir: str = "",
        folder_mode: bool = False,
        file_type: str = "",
        multi_select: bool = False,
    ) -> list[str]:
        """Invoke a file dialog for selecting one or more file paths.

        Args:
            title: Title of dialog.
            starting_dir: Starting location of dialog.
            folder_mode: If True, dialog will browse folders instead of files.
            file_type: File extension to filter for.
                       Applicable only when browsing files.
            multi_select: If True, allow multiple selection of files.
                          Applicable only when browsing files.

        Returns:
            A list of file/directory paths.
            If multi_select = False, the return value will be a list of size 1.
            If user cancels, list will be empty.
        """
        raise NotImplementedError()

    @abstractmethod
    def copy_to_clipboard(self, text: str) -> bool:
        """Copy given text to clipboard of relevant application.
        Default implementation copies to system clipboard.

        Args:
            text: Text to be copied.

        Returns:
            True on success.
        """
        raise NotImplementedError()

    # TODO: add these back in
    #def get_dependency_tree(self, must_exist: bool = True) -> DependencyData:
    #    """Return a DependencyData object which is the root of the
    #    dependency tree for the scene.

    #    Args:
    #        must_exist: Only return dependencies that can be found on disk.
    #    """
    #    # Return empty root node by default
    #    return DependencyData()

    #def update_dependency(
    #    self,
    #    dep: DependencyData,
    #    file_path: str,
    #) -> DependencyData:
    #    """Update an existing dependency to point to given file in current scene.

    #    Args:
    #        dep: DependencyData node which identifies the dependency to be updated.
    #        file_path: New path to set dependency to.

    #    Returns:
    #        DependencyData object describing new state of dependency.
    #        NOTE: This will be an isolated node, not including sub-dependency info.
    #    """
    #    # Do nothing by default
    #    return dep

    def env_var_marker(self, var_name: str) -> str:
        """Return the environment variable marker format for this host.

        Args:
            var_name: The environment variable name.

        Returns:
            Environment variable marker in host-specific format.
            Default implementation returns shell format: ${VAR_NAME}
        """
        return "${" + var_name + "}"
