# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import annotations  # needed for python 3.9 support

import os

import sgtk

from tank import LogManager
from tank_vendor.flow_integration_sdk.exceptions import (
    DraftExistsError,
    FlowError,
    InvalidDraftError,
)
from tank_vendor.flow_integration_sdk.globals import SOURCE_PURPOSE
from tank_vendor.flow_integration_sdk.objects import FlowVersion, FlowRevision
from tank_vendor.flow_integration_sdk.sandbox import (
    CheckoutDraftInfo,
    checkout_revision as checkout_revision_in_sandbox,
    get_draft_id,
    is_local_draft,
    read_draft_info,
)
from tank_vendor.flow_integration_sdk.utils import trace


logger = LogManager.get_logger(__name__)


@trace
def checkout_revision(
    revision_id: str, force: bool = False
) -> CheckoutDraftInfo | None:
    """Check out the given asset revision/version into sandbox.
    If the version is already checked out, offer an overwrite.
    If a different version of the same asset is already checkout out, offer an overwrite.

    Args:
        revision_id: Id of a published AM asset revision. This can also be a version id.
        force: If True, force a re-checkout even if an existing draft is found.

    Returns:
        CheckoutDraftInfo object or None if operation was cancelled.

    Raises:
        FlowError
    """
    if FlowVersion.is_version_id(revision_id):
        revision = FlowVersion(revision_id).revision
    else:
        revision = FlowRevision.get_revision(revision_id)

    try:
        draft_info = checkout_revision_in_sandbox(
            revision._revision,
            component_purpose=SOURCE_PURPOSE,
            force=force,
        )
    except DraftExistsError:
        draft_info = _handle_existing_draft(revision)
        if draft_info is None:
            # Operation was cancelled so exit
            return None

    # Open checked out draft file
    flow_host = sgtk.platform.current_engine().flow_host
    if flow_host:
        draft_path = draft_info.source_path
        logger.info(f"Opening draft path: {draft_path}")
        flow_host.open_file(draft_path)

    return draft_info


@trace
def _handle_existing_draft(revision: FlowRevision) -> CheckoutDraftInfo | None:
    """Called during a checkout operation when an existing draft is detected
    to handle the situation as safely as possible. If host class is available,
    pop-up a dialog to ask the user what to do, otherwise output an informative
    message and cancel the operation.

    NOTE: We are only concerned with versions here and not the granularity of
          revisions. This is because we are assuming that binaries and dependencies
          (i.e. components and uses relationships) cannot change between revisions
          of the same version. Therefore, checking out any given revision of a version
          should be sufficient for ensuring that we fetch and copy the correct binaries.

    Returns CheckoutDraftInfo object if successful, or None if operation is cancelled.
    """
    draft_id = get_draft_id(revision.id)
    try:
        draft_info = read_draft_info(draft_id)
        checkout_version = draft_info.version
        checkout_revision = draft_info.revision
    except InvalidDraftError:
        # This indicates that the draft is corrupted
        checkout_version = None

    # If not host is available, just cancel the operation
    flow_host = sgtk.platform.current_engine().flow_host
    if flow_host is None:
        msg = "There is an existing draft detected with checkout version: "
        msg += f"{checkout_version}."
        logger.error(msg)
        return None

    title = "Existing draft detected"
    if checkout_version is None:
        # Warning to user with options to
        # 0 - overwrite existing draft
        # 1 - cancel
        msg = "There is an existing draft which is corrupted. "
        msg += "Would you like to overwrite this with a fresh checkout?"
        options = ["New checkout", "Cancel"]

        action_idx = flow_host.dialog(
            title=title,
            msg=msg,
            buttons=options,
            default=1,  # cancel by default
            no_ui_option=1,  # cancel when no dialog can be launched
        )
        action = options[action_idx]

    elif checkout_version == revision.version_number:
        # Warning to user with options to
        # 0 - overwrite existing draft
        # 1 - proceed with existing draft
        msg = "This version is already checked out in sandbox. "
        msg += "Would you like to overwrite this with a fresh checkout?"
        options = ["New checkout", "Use original checkout"]

        action_idx = flow_host.dialog(
            title=title,
            msg=msg,
            buttons=options,
            default=1,  # use original by default
            no_ui_option=1,  # use original when no dialog can be launched
        )
        action = options[action_idx]

    else:
        # Warning to user with options to
        # 1 - overwrite existing draft
        # 2 - cancel
        msg = f"An existing checkout already exists of version {checkout_version} "
        msg += f"(r{checkout_revision}) of this asset. Would you like to overwite "
        msg += f"this with a checkout of version {revision.version_number} "
        msg += f"(r{revision.revision_number})?"
        options = ["New checkout", "Cancel"]

        action_idx = flow_host.dialog(
            title=title,
            msg=msg,
            buttons=options,
            default=1,  # cancel by default
            no_ui_option=1,  # cancel when no dialog can be launched
        )
        action = options[action_idx]

    if action == "New checkout":
        # Force a new checkout
        return checkout_revision_in_sandbox(
            revision._revision,
            component_purpose=SOURCE_PURPOSE,
            force=True,
        )
    elif action == "Use original checkout":
        msg = f"Using original draft of version {checkout_version} "
        msg += f"(r{checkout_revision})."
        logger.info(msg)
        return draft_info
    else:
        logger.warning("Checkout operation cancelled.")
        return None


@trace
def open_draft(draft_id: str):
    """Open draft source file for editing if draft is local.

    Args:
        draft_id: Unique id that identifies a draft location in local sandbox.

    Raises:
        FlowError
        InvalidDraftError
    """
    flow_host = sgtk.platform.current_engine().flow_host
    if not flow_host:
        raise FlowError(
            "Opening a draft must be done in an engine which supports Flow integration."
        )

    if not is_local_draft(draft_id):
        msg = f'The draft "{draft_id}" is not in local sandbox.'
        raise InvalidDraftError(draft_id=draft_id, details=msg)

    draft_info = read_draft_info(draft_id)
    draft_path = draft_info.source_path
    if not os.path.exists(draft_path):
        msg = f'Corrupted draft folder. The file "{draft_path}" does not exist.'
        raise InvalidDraftError(draft_id=draft_id, details=msg)

    # Open file
    logger.info(f"Opening file: {draft_path}")
    flow_host.open_file(draft_path)
