# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Test utility to read query config and generate a printed hierarchy.
"""
import json
import os
import re
from typing import Any

from tank_vendor.flow_integration_sdk.objects import FlowAsset, FlowProject
from tank_vendor.flow_integration_sdk.utils import get_logger


# Read query config
QUERY_CONFIG = None
with open(f"{os.path.dirname(__file__)}/fd_query_config.json") as f:
    config_str = f.read()
    QUERY_CONFIG = json.loads(config_str)

# Store project id globally for convenience
PROJECT_ID = None


class TreeItem:
    """A node in a federated hierarchy tree.

    Instances contain
        - UI specifications for the tree item
        - The ability to query its children
    """

    def __init__(
        self,
        label: str,
        icon: str | None = None,
        color: str | None = None,
        asset: FlowAsset | None = None,
    ):

        # UI attributes
        self.label = label
        self.icon = icon
        self.color = color

        # Asset association (medm)
        self.asset = asset

        # Sub-query context
        self._child_filters = {}
        self._child_path_tokens = []

        # Child items
        self.children = []

    def get_children(self):
        """Retrieve list of children under this tree item."""
        if self._child_path_tokens:
            self.children = _generate_items(
                parent=self,
                path_tokens=self._child_path_tokens,
                parent_filters=self._child_filters,
                recursive=False,
            )
        else:
            self.children = []

    def pprint(self, filestream=None, recurse=True, num_tabs=0):
        """Print tree item to standard out of filestream if provided.
        Recurse on children if recurse = True.
        """
        strs = [
            num_tabs * "\t" + "----------------------------------------------------"
        ]
        if self.asset:
            strs.append(num_tabs * "\t" + f"{self.label} - {self.asset.type_ids[0]}")
        else:
            strs.append(num_tabs * "\t" + self.label)
        if self.icon:
            strs.append(num_tabs * "\t" + f"icon: {self.icon}")
        if self.color:
            strs.append(num_tabs * "\t" + f"color: {self.color}")
        strs.append(
            num_tabs * "\t" + "----------------------------------------------------"
        )

        if filestream:
            for s in strs:
                filestream.write(s + "\n")
        else:
            for s in strs:
                print(s)

        if recurse:
            for child in self.children:
                child.pprint(filestream, recurse, num_tabs + 1)


def _resolve_filter(data_obj, resolver: str | None) -> Any:
    """Given some kind of data object, resolve it based on
    resolution specifications provided.

    The following notation is supported:
        * COMPONENT(name=<component name>) -> resolves to component of matching name
        * PROPERTY(<property_name>) -> resolves to the value of the property of a component
        * ATTRIBUTE(<attribute_name>) -> resolves to the value of the attribute of any object
        * DATA -> the original data object

    NOTE: A property may be a reference property, indicated with a "$id:" prefix
          i.e. PROPERTY($id:targetAsset) -> will resolve to the target asset
          If the property is an "array" type, an array of asset ids will be returned.

    The above resolution steps can be chained together using ".".
    Resolution tokens should be surrounded by {}.

    Example:
        Input string = "Hello {DATA.COMPONENT(name=Employee Info).PROPERTY(firstName)}!"

        For an employee named "Bob" should give the result "Hello Bob!".
    """
    if resolver:
        resolver = resolver.split(".")
    else:
        resolver = []

    result = data_obj

    for resolution_step in resolver:
        m = re.match(r"(?P<res_type>.+)\((?P<res_condition>.+)\)", resolution_step)
        if m:
            res_type = m.group("res_type")
            res_condition = m.group("res_condition")
        else:
            res_type = resolution_step
            res_condition = None

        if res_type == "COMPONENT":
            # Search for component matching name
            # (input source should be an asset)
            prop, value = res_condition.split("=")
            cmd = f"result.find_component({prop}='{value}')"
            result = eval(cmd)

        elif res_type == "PROPERTY":
            # Get the value of the property
            # NOTE: Properties refer specifically to properties
            #       on a component, while attributes refer to member
            #       variables of any object.
            prop_name = res_condition
            if prop_name.startswith("$id:"):
                # If the property is a reference, convert the id into an asset object
                prop_name = res_condition[4:]
                ref_id = eval(f"result.properties.get('{prop_name}')")
                # Handle lists automatically
                if isinstance(ref_id, list):
                    result = []
                    for r_id in ref_id:
                        result.append(FlowAsset(r_id["objectId"]["id"]))
                else:
                    ref_asset = FlowAsset(ref_id)
                    result = ref_asset
            else:
                result = eval(f"result.properties.get('{prop_name}')")

        elif res_type == "ATTRIBUTE":
            # Get the value of the attribute on an object
            attr_name = res_condition
            result = eval(f"result.{attr_name}")

        elif res_type == "DATA":
            continue

    return result


def _resolve_string_tokens(data_obj, string):
    """Resolve any nested tokens within a string value."""

    result = ""
    token = ""
    in_token = False

    for c in string:
        if c == "{":
            token = ""
            in_token = True
        elif c == "}":
            in_token = False
            resolved_value = _resolve_filter(data_obj, token)
            result += resolved_value
        elif in_token:
            token += c
        else:
            result += c

    return result


def _resolve_items(config: dict, parent: TreeItem, parent_filters: dict):
    """Use the resolution criteria provided by the config dictionary to
    generate a list of TreeItems.
    """
    from .fd_project_setup import _medm_search

    # UI configuration - may contain tokens to be resolved
    label_config = config.get("label")
    icon_config = config.get("icon")
    color_config = config.get("color")

    # Data resolution
    # When resolving items, the final data object that we end up with
    # may be of different types (e.g. asset, component, literal value)
    # depending on the resolution criteria, which may be multi-tiered.
    res_config = config.get("resolution")
    # A search filter indicates that a search query should be made
    # using this filter
    q_filter = res_config.get("search_filter")
    # The presence of an additional "assets resolver" indicates that
    # the first asset of the search result should be further
    # resolved using this resolution method to establish a new list of assets.
    # NOTE: the result of an "assets resolver" should be a new list of assets.
    assets_resolver = res_config.get("assets_resolver")
    # A data resolver further refines an asset result to drill down to
    # the piece of data that is relevant for the tree item.
    # It is from this object's standpoint that 'DATA' variables are resolved.
    data_resolver = res_config.get("data_resolver")

    # Parent items can pass on additional filters
    # Append any search filters passed down from the parent
    if parent_filters and parent_filters.get("search_filter"):
        q_filter += ";" + parent_filters.get("search_filter")

    # Intial filter pass
    # ------------------
    # If a parent passes along an "assets_resolver", this means that
    # we can use the parent's asset to provide an asset list using the given
    # resolution method.
    # In this case, there is no need to perform a search query,
    # even if a search filter is provided in our resolution config.
    if parent_filters and parent_filters.get("assets_resolver"):
        parent_assets_resolver = parent_filters.get("assets_resolver")
        assets = _resolve_filter(parent.asset, parent_assets_resolver)
    elif q_filter:
        assets = _medm_search(PROJECT_ID, q_filter)
    else:
        raise RuntimeError("Asset filter criteria is missing.")

    # Secondary filter pass
    # ---------------------
    # Perform a secondary "assets resolver" if specified.
    # This will give us a new list of assets using the first
    # asset from the initial filter pass.
    if assets_resolver:
        if not assets:
            raise RuntimeError(
                "Cannot run secondary 'assets_resolver'. Initial filter result is empty."
            )
        assets = _resolve_filter(assets[0], assets_resolver)

    # Now that we have a list of assets, build a tree item
    # to represent each.
    items = []
    for asset in assets:
        # Distill down to the data source we need
        # Remember, this could be resolved to any type
        data_obj = _resolve_filter(asset, data_resolver)

        icon_value = color_value = None
        # The data object becomes the focal point for resolving
        # any variables within UI properties and child filters
        label_value = _resolve_string_tokens(data_obj, label_config)
        if icon_config:
            icon_value = _resolve_string_tokens(data_obj, icon_config)
        if color_config:
            color_value = _resolve_string_tokens(data_obj, color_config)

        items.append(
            TreeItem(
                label=label_value,
                icon=icon_value,
                color=color_value,
                asset=asset,
            )
        )

    return items


def _generate_items(
    parent: TreeItem,
    path_tokens: list[str],
    parent_filters: dict | None = None,
    recursive=False,
):
    """Generate the list of items that is the result of querying
    MEDM based on the next token in the token list provided.

    Raises:
        RuntimeError
    """
    logger = get_logger(__name__)

    if not path_tokens:
        return []

    token = path_tokens.pop(0)
    logger.info(f"Generating items for token: {token}...")

    config = QUERY_CONFIG.get(token)
    if config is None:
        msg = f'Invalid query token provided: "{token}".'
        logger.error(msg)
        raise RuntimeError(msg)

    kind = config.get("kind")  # static or dynamic?

    if kind == "static":
        # For static tokens, all values should be literal
        label = config.get("label")
        icon = config.get("icon")
        items = [TreeItem(label=label, icon=icon)]

    elif not config.get("resolution"):
        # All dyanmic tokens are expected to have a resolution config
        raise RuntimeError(
            f'Non-static token "{token}" missing "resolution" configuration.'
        )

    else:
        # Resolve dynamic tokens into a list of new tree items
        items = _resolve_items(config, parent, parent_filters)

    items_list = "\n\t".join([item.label for item in items])
    logger.info(f"Generated {len(items)} items for token: {token}\n\t{items_list}")

    if len(path_tokens) == 0:
        return items

    # If there are still path tokens left, must prepare the tree items
    # for being able to find their children (either now or later).

    # Child filters are filters that must be passed on to the resolution
    # criteria of my children. An item may have different child filters for
    # different entity types.
    child_filters = config.get("child_filters") or {}
    # The next token in the path is the token that determines what my children are
    # Strip this value down to its basic state in order to match it to the
    # applicable "child filter" if found.
    next_token = path_tokens[0].strip("{}").lower()

    for item in items:
        child_filter = {}
        for ent_type, ent_filters in child_filters.items():
            if ent_type == next_token:
                # For each entity type, there may be multiple filters
                # Each one may have variables that need to be resolved using
                # the current item's information.
                for filter_type, filter_str in ent_filters.items():
                    child_filter[filter_type] = _resolve_string_tokens(
                        item.asset, filter_str
                    )
        # Once we've resolved the filters, make sure to save it for future reference
        # (The tree nodes may be expanded on demand, so we may not get the next level of
        # children until later.)
        item._child_filters = child_filter
        item._child_path_tokens = list(path_tokens)
        # Only query the next level if requested
        if recursive:
            item.children = _generate_items(
                item, list(path_tokens), child_filter, recursive=True
            )

    return items


def get_tree_root(project_id: str, hierarchy_path: str) -> TreeItem:
    """Return root of federated hierarchy tree."""
    global PROJECT_ID

    PROJECT_ID = project_id

    # Create a root tree item representing the project
    project = FlowProject(project_id)
    root = TreeItem(label=f"PROJECT: {project.name}")

    path_tokens = hierarchy_path.split("/")
    root._child_path_tokens = path_tokens

    return root


def generate_hierarchy(project_id: str, hierarchy_path: str) -> TreeItem:
    """Generate a hierarchy of TreeItems for given MEDM project
    based on the hierarchy path provided. The tokens in the hierarchy path
    will be used as keys into the QUERY_CONFIG which will dictate how
    the tree is populated.

    Args:
        project_id: MEDM project id.
        hierarchy_path: Toolkit-esque template path such as "assets/{sg_asset_type}/{Asset}".
                        Supported tokens:
                            * assets -> static value grouping all SG Asset entities.
                            * shots -> static value grouping all SG Shot entities.
                            * sequences -> static value grouping all SG Sequence entities.
                            * {sg_asset_type} -> token value grouping SG Assets of a certain SG Asset Type.
                            * {Step} -> token value grouping all assets associated with a SG Pipeline Step.
                            * {Asset} -> token value grouping all assets associated with a SG Asset entity.
                            * {Episode} -> token value grouping all assets associated with a SG Episode entity.
                            * {Sequence} -> token value grouping all assets associated with a SG Sequence entity.
                            * {Shot} -> token value grouping all assets associated with a SG Shot entity.

    Returns:
        A root TreeItem.
    """
    global PROJECT_ID

    PROJECT_ID = project_id
    logger = get_logger(__name__)

    # Create a root tree item representing the project
    project = FlowProject(project_id)
    root = TreeItem(label=f"PROJECT: {project.name}")

    # This list will be modified by the _generate_items() function
    path_tokens = hierarchy_path.split("/")

    # Recursively generate the tree
    logger.info("====================================")
    logger.info("GENERATE FEDERATED HIERARCHY...")
    items = _generate_items(root, path_tokens, recursive=True)
    root.children = items
    logger.info("HIERARCHY GENERATION COMPLETE!")
    logger.info("====================================")

    return root
