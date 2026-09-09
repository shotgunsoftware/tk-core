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
        # Map of ancestor tags to FlowAsset objects
        # An ancestor tag is derived from an upstream token
        # within the token path.
        # Example: with a path like "{Asset}/{Step} you can create
        # ancestor tags like "ASSET", "STEP".  These tags can be used
        # as string tokens within the config that can then be resolved
        # at runtime with the value of the associated ancestor asset.
        self._ancestors = {}

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
                ancestors=self._ancestors,
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


def _resolve_filter(
    data_obj, resolver: str | None, ancestors: dict | None = None
) -> Any:
    """Given some kind of data object, resolve it based on
    resolution specifications provided.

    The following notation is supported:
        * COMPONENT(name=<component name>) -> resolves to component of matching name
        * PROPERTY(<property_name>) -> resolves to the value of the property of a component
        * ATTRIBUTE(<attribute_name>) -> resolves to the value of the attribute of any object
        * DATA -> the original data object

    As well, arbitrary ancestor tags can be used provided that it exists in
    the provided `ancestor` dictionary. (e.g. ASSET, STEP, etc.)
    Within the dictionary, these tags should map to a FlowAsset object which can then
    be used to resolve any remaining tokens.

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
        resolution_steps = resolver.split(".")
    else:
        resolution_steps = []

    result = data_obj
    ancestors = ancestors or {}

    for resolution_step in resolution_steps:
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

        elif res_type in ancestors:
            # Grab the object associated with the ancestor tag
            # (e.g. ASSET, SHOT, etc.)
            result = ancestors[res_type]

        else:
            # Not a recognizable token, return early with value of current step
            #
            # This is hacky but it works.
            # There are two situations in which we might encounter an unrecognizable token:
            #   1. The token is actually not meant to be resolved and should remain
            #      unchanged.
            #           - Will happen in the case of the 'disable_tokens' config attibute
            #             which will include names of existing path tokens (e.g. "{Sequence}")
            #   2. The token is an ancestor tag which does not exist in the current
            #      ancestor map.
            #           - May happen within a search filter where multiple ancestor types
            #             are used with an "or" operator. Only one of the ancestor types
            #             will resolve and the others might not exist.
            #           - In this case, we need to return _some_ string, and it should not
            #             be blank or contain any illegal characters (such as '.') that will
            #             break the search query. Returning just the current resolution step is safe because
            #             will ensure there are no illegal characters. And since this
            #             condition can't be resolved anyway, we know it is irrelevant to
            #             the query result so which string value we use really doesn't matter.
            return resolution_step

    return result


def _resolve_string_tokens(data_obj, string, ancestors):
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
            resolved_value = _resolve_filter(data_obj, token, ancestors)
            if resolved_value == token:
                # No change indicates this was not a resolvable
                # token, but a literal - leave value unchanged
                result += "{" + resolved_value + "}"
            else:
                result += resolved_value
        elif in_token:
            token += c
        else:
            result += c

    return result


def _resolve_items(
    config: dict, parent: TreeItem, parent_filters: dict, ancestors: dict
) -> list[TreeItem]:
    """Use the resolution criteria provided by the config dictionary to
    generate a list of TreeItems.

    (See `_generate_items_for_token` for argument info.)
    """
    from .fd_project_setup import _medm_search

    logger = get_logger(__name__)

    # UI configuration - may contain tokens to be resolved
    label_config = config.get("label")
    icon_config = config.get("icon")
    color_config = config.get("color")

    # Data resolution
    # When resolving items, the final data object that we end up with
    # may be of different types (e.g. asset, component, literal value)
    # depending on the resolution criteria, which may be multi-tiered.
    res_config = config.get("resolution", {})
    # A search filter indicates that a search query should be made
    # using this filter
    q_filter = res_config.get("search_filter", "")
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
        assets = _resolve_filter(parent.asset, parent_assets_resolver, ancestors)
    elif q_filter:
        # De-duplicate filters here before querying
        # Since we accumulate filters down a token path, conditions could
        # very well be repeated along the way
        # Also remove any empty conditions which will cause an error
        unique_filter_list = list(dict.fromkeys(q_filter.split(";")))
        if "" in unique_filter_list:
            unique_filter_list.remove("")
        q_filter = ";".join(unique_filter_list)
        assets = _medm_search(PROJECT_ID, q_filter)
    else:
        # Not every branch of a token path may end up with legitimate filter criteria
        # This is ok - provide a warning and move on.
        logger.warning("Asset filter criteria is missing - skipping item resolution...")
        return []

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
        assets = _resolve_filter(assets[0], assets_resolver, ancestors)

    # Now that we have a list of assets, build a tree item
    # to represent each.
    items = []
    for asset in assets:
        # Distill down to the data source we need
        # Remember, this could be resolved to any type
        data_obj = _resolve_filter(asset, data_resolver, ancestors)

        icon_value = color_value = None
        # The data object becomes the focal point for resolving
        # any variables within UI properties and child filters
        label_value = _resolve_string_tokens(data_obj, label_config, ancestors)
        if icon_config:
            icon_value = _resolve_string_tokens(data_obj, icon_config, ancestors)
        if color_config:
            color_value = _resolve_string_tokens(data_obj, color_config, ancestors)

        items.append(
            TreeItem(
                label=label_value,
                icon=icon_value,
                color=color_value,
                asset=asset,
            )
        )

    return items


def _generate_items_for_token(
    token: str,
    parent: TreeItem,
    path_tokens: list[str],
    parent_filters: dict,
    recursive: bool = False,
    ancestors: dict | None = None,
):
    """Generate the list of items that is the result of performing
    the resolution designated by the given query config.

    Args:
        token: The current token being processed.
        parent: The TreeItem that the generated items should be parented under.
        path_tokens: The rest of the path tokens to be processed by children.
        parent_filters: An accumulated dictionary of fully resolved 'child_filters'
                        coming from all previous ancestors / resolution steps.
        recursive: If True, generate the entire tree.
                   Otherwise, generate only the next level of items.
        ancestors: A dictionary of previously processed tokens and their
                   associated FlowAsset object within the context of the current
                   location within the hierarchy tree.
                        * key = ASSET TAG -> capitalized token name
                        * value = FlowAsset object

    Raises:
        RuntimeError
    """
    logger = get_logger(__name__)

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

    elif not config.get("resolution") and not parent_filters:
        # All dyanmic tokens are expected to have some resolution criteria
        # whether via it's own resolution config, or some parent filters
        raise RuntimeError(
            f'Non-static token "{token}" missing "resolution" configuration.'
        )

    else:
        # Resolve dynamic tokens into a list of new tree items
        # For the resolution, grab only the parent filters that are relevant
        # to the current token
        filter_type = token.lower().strip("{}")
        parent_filters_for_type = parent_filters.get(filter_type, {})
        items = _resolve_items(config, parent, parent_filters_for_type, ancestors)

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
    # Translate the current token to an "ancestor tag" which will be used
    # as a key for the ancestor map passed to our children.
    ancestor_tag = token.upper().strip("{}")

    for item in items:
        # We will create a copy of the child filters with resolved values
        # based on the current item context
        resolved_child_filters = {}
        for ent_type, ent_filters in child_filters.items():
            # For each entity type, there may be multiple filters
            # Each one may have variables that need to be resolved using
            # the current item's information.
            resolved_child_filters[ent_type] = {}
            for filter_type, filter_str in ent_filters.items():
                if isinstance(filter_str, list):
                    # Some filters may be lists, so resolve each list item
                    new_filter = []
                    for f in filter_str:
                        new_filter.append(
                            _resolve_string_tokens(item.asset, f, ancestors)
                        )
                    resolved_child_filters[ent_type][filter_type] = new_filter
                else:
                    resolved_child_filters[ent_type][filter_type] = (
                        _resolve_string_tokens(item.asset, filter_str, ancestors)
                    )

        # We will also carry forward any filters from our parent
        # Merge into the same dictionary
        for ent_type, ent_filters in parent_filters.items():
            if ent_type not in resolved_child_filters:
                resolved_child_filters[ent_type] = {}
            for filter_type, filter_str in ent_filters.items():
                if filter_type in resolved_child_filters[ent_type]:
                    if isinstance(filter_str, list):
                        resolved_child_filters[ent_type][filter_type].append(filter_str)
                    else:
                        resolved_child_filters[ent_type][filter_type] += (
                            ";" + filter_str
                        )
                else:
                    resolved_child_filters[ent_type][filter_type] = filter_str

        # Once we've resolved the filters, make sure to save it for future reference
        # (The tree nodes may be expanded on demand, so we may not get the next level of
        # children until later.)
        item._child_filters = resolved_child_filters
        item._child_path_tokens = list(path_tokens)
        # Also create a copy of the current ancestor map and add myself to it
        # so my children can resolve any ancestor tags pointing to me in their config
        child_ancestors = ancestors.copy() if ancestors else {}
        if item.asset:
            child_ancestors[ancestor_tag] = item.asset
        item._ancestors = child_ancestors

        # Only query the next level if requested
        if recursive:
            item.children = _generate_items(
                item,
                list(path_tokens),
                resolved_child_filters,
                recursive=True,
                ancestors=child_ancestors,
            )

    return items


def _generate_items(
    parent: TreeItem,
    path_tokens: list[str],
    parent_filters: dict | None = None,
    recursive: bool = False,
    ancestors: dict | None = None,
):
    """Generate the list of items that is the result of querying
    MEDM based on the next token in the token list provided.

    (See `_generate_items_for_token` for argument info.)
    """
    logger = get_logger(__name__)

    if not path_tokens:
        return []

    token = path_tokens.pop(0)
    logger.info(f"Processing path token: {token}...")
    # The token itself may be a concatenation of multiple tokens
    # Process each one and concatenate the results
    tokens = token.split("+")

    items = []
    for tk in tokens:
        logger.info(f"Processing sub-token: {token}...")

        # A single token may have multiple related queries that should
        # be concatenated together
        # The family of tokens will denoted by "<TOKEN>" or "<TOKEN>+<some name>"

        # Parent configs can specify certain tokens to be ignored among its
        # child config family.
        parent_filters = parent_filters or {}
        disabled_tokens = parent_filters.get("disable_tokens", [])
        for key in QUERY_CONFIG:
            if key in disabled_tokens:
                continue  # skip disabled tokens
            if key == tk or key.startswith(tk + "+"):
                logger.info(f"Generating items for related token: {key}...")
                items.extend(
                    _generate_items_for_token(
                        token=key,
                        parent=parent,
                        path_tokens=list(path_tokens),
                        parent_filters=parent_filters,
                        recursive=recursive,
                        ancestors=ancestors,
                    )
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
