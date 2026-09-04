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
# +

"""
This module contains medm querying convenience utilities.
"""

from __future__ import annotations  # needed for python 3.9 support

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .exceptions import FlowError
from .globals import get_client
from .objects import FlowAsset
from .utils import trace


def generate_search_filter(
    name: str = "",
    type_id: str = "",
    components: dict | None = None,
) -> str:
    """Build MEDM API supported search query filter for the criteria
    specified.

    Args:
        name: If specified, search for assets with this name.
        type_id: If specified, search for assets that contain
                 a type component with this type id.
        components: Dictionary of format:
                        {COMPONENT TYPE ID: {COMPONENT PROPERTY: PROPERTY VALUE}}
                    Search for assets that contain a component of the given type.
                    If property mappings are provided, further filter for assets
                    where the components have the given property values.

                    NOTE: Complex COMPONENT PROPERTIES can be drilled into via '.'
                          notation. (e.g. the MEDM id of a reference property can be
                          accessed via "<property>.objectId.id")

                    NOTE: Values are treated as strings for now.

    Returns:
        String filter that can be used in medm_search() function.
    """
    filter_str = ""

    if name:
        filter_str += f"attribute.name=='{name}';"
    if type_id:
        filter_str += f"components.typeId=='{type_id}';"
    if components:
        for comp_type_id, d_props in components.items():
            for prop, value in d_props.items():
                filter_str += f"components[{comp_type_id}].{prop}=='{value}';"

    return filter_str.strip(";")


@trace
def medm_search(
    project_id: str,
    q_filter: str,
    parent_id: str = "",
    include_deleted: bool = False,
) -> list[FlowAsset]:
    """Perform global search in MEDM under given project with provided
    filter criteria.

    NOTE: This search automatically filters out deleted assets.

    Args:
        project_id: Id of project to search under.
        q_filter: Filter criteria following MEDM api specs.
                  See https://git.autodesk.com/learning-content/flow/blob/master/clc/AM-DevGuide/source/dg-using-filters.md
        parent_id: Specify a parent to scope search to. This will
                   limit the search to direct children of this parent.
        include_deleted: Include deleted assets in search results.

    Returns:
        List of FlowAsset objects.

    Raises:
        FlowError
    """
    client = get_client()

    # Search under parent, and only include non-deleted assets
    q_filter_pre = ""
    if not include_deleted:
        q_filter_pre = "attribute.deletionState=='NOT_DELETED';"
    if parent_id:
        q_filter_pre += f"attribute.parentId=={parent_id};"

    q_input = medm_model.AssetsBySearchInput(
        project_ids=[project_id],
        filter=q_filter_pre + q_filter,
    )
    q_search = client.service_asset.assets_by_search(q_input)

    try:
        q_search.call()
    except GQLAPIError as exc:
        msg = f"Search query failed. {exc}"
        raise FlowError(msg) from exc

    result = [FlowAsset(a) for a in q_search.results]
    return result
