# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
# +

"""
This module contains custom exception classes.
"""

from __future__ import annotations  # needed for python 3.9 support


class FlowError(RuntimeError):
    """Base error class for Flow asset management errors."""

    def __init__(
        self, message, *args, details: str = "", data: dict | None = None, **kwargs
    ):
        """
        Args:
            message: Base message for exception.
            details: Additional information.
            data: Any additional data relevant to the error.
                  Stored as a dictionary of key-value pairs.
        """
        if details:
            message = f"{message} {details}"
        super().__init__(message, *args, **kwargs)
        self.data = data


class CreateAssetError(FlowError):
    def __init__(self, *args, **kwargs):
        message = "Could not create asset."
        super().__init__(message, *args, **kwargs)


class ComponentSpecError(FlowError):
    def __init__(self, *args, **kwargs):
        message = "Invalid component spec provided."
        super().__init__(message, *args, **kwargs)


class ConfigurationError(FlowError):
    def __init__(self, *args, **kwargs):
        message = "Flow settings have not been configured correctly."
        super().__init__(message, *args, **kwargs)


class DirectoryNotCreatedError(FlowError):
    def __init__(self, *args, dir_path: str, **kwargs):
        message = f'Couldn\'t create directory "{dir_path}".'
        super().__init__(message, *args, **kwargs)


class DraftExistsError(FlowError):
    def __init__(self, *args, draft_id: str, draft_folder: str, **kwargs):
        """
        Args:
            draft_id: Id that uniquely identifies a draft in local sandbox.
            draft_folder: Path to draft folder in local sandbox.
        """
        message = f'The draft "{draft_id}" already exists at {draft_folder}.'
        super().__init__(message, *args, **kwargs)
        self.draft_id = draft_id
        self.draft_folder = draft_folder


class EntityNotFoundError(FlowError):
    """Thrown when a given MEDM entity id is invalid, and cannot be used to
    successfully query the entity.
    """

    def __init__(self, *args, entity_id: str, **kwargs):
        """
        Args:
            entity_id: Id for an Asset or Project.
        """
        message = f'Entity id "{entity_id}" is invalid.'
        super().__init__(message, *args, **kwargs)
        self.entity_id = entity_id


class FileUploadError(FlowError):
    def __init__(self, *args, file_path: str, **kwargs):
        message = f"Error uploading file {file_path}."
        super().__init__(message, *args, **kwargs)


class InvalidDraftError(FlowError):
    def __init__(self, *args, draft_id: str, **kwargs):
        """
        Args:
            draft_id: Id that uniquely identifies a draft in local sandbox.
        """
        message = f'Draft id "{draft_id}" is invalid.'
        super().__init__(message, *args, **kwargs)
        self.draft_id = draft_id


class PublishAssetError(FlowError):
    def __init__(self, *args, **kwargs):
        message = "Could not publish asset."
        super().__init__(message, *args, **kwargs)


class PublishConflictError(FlowError):
    def __init__(
        self, *args, asset, checkout_version: int, checkout_revision: int, **kwargs
    ):
        message = "A publish conflict has been detected. New revisions of the asset "
        message += f"have been published since version {checkout_version} "
        message += f"(r{checkout_revision}) was checked out. "
        message += f"The latest revision is now {asset.version_number} "
        message += f"(r{asset.revision_number})."

        super().__init__(message, *args, **kwargs)
        self.asset = asset
        self.checkout_version = checkout_version
        self.checkout_revision = checkout_revision
