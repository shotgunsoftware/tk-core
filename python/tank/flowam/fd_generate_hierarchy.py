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

# Cache asset objects to avoid redundant querying
# key = asset id, value = FlowAsset
ASSET_CACHE = {}


class TreeItem:

    def __init__(
        self,
        label: str,
        asset: FlowAsset | None = None,
        icon: str | None = None,
        color: str | None = None,
        children: list | None = None,
    ):

        self.label = label
        self.asset = asset
        self.icon = icon
        self.color = color
        self.children = children or []

    def add_child(self, item):
        """Add child tree item to list of children."""
        self.children.append(item)

    def pprint(self, filestream=None, recurse=True, num_tabs=0):
        """Print tree item to standard out of filestream if provided.
        Recurse on children if recurse = True.
        """
        strs = [num_tabs*"\t" + "----------------------------------------------------"]
        if self.asset:
            strs.append(num_tabs*"\t" + f"{self.label} - {self.asset.type_ids[0]}")
        else:
            strs.append(num_tabs*"\t" + self.label)
        if self.icon:
            strs.append(num_tabs*"\t" + f"icon: {self.icon}")
        if self.color:
            strs.append(num_tabs*"\t" + f"color: {self.color}")
        strs.append(num_tabs*"\t" + "----------------------------------------------------")

        if filestream:
            for s in strs:
                filestream.write(s+"\n")
        else:
            for s in strs:
                print(s)

        if recurse:
            for child in self.children:
                child.pprint(filestream, recurse, num_tabs+1)


def _resolve_item_value(item_entity, item_resolution: str | None) -> Any:
    """Given some kind of item entity, resolve it based on the item
    resolution guidance provided.
    """
    if item_resolution:
        item_resolution = item_resolution.split(".")
    else:
        item_resolution = []

    result = item_entity

    for resolution_step in item_resolution:
        m = re.match(r"(?P<res_type>.+)\((?P<res_condition>.+)\)", resolution_step)
        if m:
            res_type = m.group("res_type")
            res_condition = m.group("res_condition")
        else:
            res_type = resolution_step
            res_condition = None
        print('res_type:', res_type)
        print('res_condition:', res_condition)

        if res_type == "COMPONENT":
            prop, value = res_condition.split("=")
            cmd = f"result.find_component({prop}='{value}')"
            result = eval(cmd)
        elif res_type == "PROPERTY":
            print('property...')
            prop_name = res_condition
            if prop_name.startswith("$id:"):
                print('ref property...')
                prop_name = res_condition[4:]
                ref_id = eval(f"result.properties.get('{prop_name}')")
                if isinstance(ref_id, list):
                    print('list ref')
                    result = []
                    for r_id in ref_id:
                        result.append(FlowAsset(r_id["objectId"]["id"]))
                else:
                    print('single ref')
                    ref_asset = FlowAsset(ref_id)
                    result = ref_asset
            else:
                result = eval(f"result.properties.get('{prop_name}')")
        elif res_type == "ATTRIBUTE":
            attr_name = res_condition
            result = eval(f"result.{attr_name}")
        elif res_type == "ITEM":
            continue

    return result


def _resolve_string_tokens(item_entity, string):
 
    result = ""
    token = ""
    in_token = False

    print('resolving string:', string)

    for c in string:
        if c == "{":
            token = ""
            in_token = True
        elif c == "}":
            in_token = False
            resolved_value = _resolve_item_value(item_entity, token)
            print('token:', token, '->', resolved_value)
            result += resolved_value
        elif in_token:
            token += c
        else:
            result += c

    print('resolved value:', result)
    return result


def _resolve_items(config: dict, parent: TreeItem, parent_filters: dict):
    """Resolve the current item based on resolution criteria
    provided by config dictionary.
    """
    from .fd_project_setup import _medm_search

    res_config = config.get("resolution")
    q_filter = res_config.get("search_filter")
    label_config = config.get("label")
    icon_config = config.get("icon")
    color_config = config.get("color")
    item_resolution = res_config.get("item")
    items_resolution = res_config.get("items")

    print(config)
    print(res_config)

    if parent_filters and parent_filters.get("search_filter"):
        q_filter += ';' + parent_filters.get("search_filter")
    print('q_filter:', q_filter)

    if parent_filters and parent_filters.get("asset_filter"):
        assets_resolution = parent_filters.get("asset_filter")
        assets = _resolve_item_value(parent.asset, assets_resolution)
    elif q_filter:
        assets = _medm_search(PROJECT_ID, q_filter)
    else:
        raise RuntimeError("Asset filter criteria is missing.")

    print('assets 1:', assets)
    if items_resolution:
        if not assets:
            raise RuntimeError("No assets in initial filter.")
        assets = _resolve_item_value(assets[0], items_resolution)
        print('assets 2:', assets)

    items = []
    for asset in assets:
        item_value = _resolve_item_value(asset, item_resolution)
        
        print('label value...')
        label_value = _resolve_string_tokens(item_value, label_config)
        
        print('icon value...')
        icon_value = None
        if icon_config:
            icon_value = _resolve_string_tokens(item_value, icon_config)
        print('color value...')
        color_value = None
        if color_config:
            color_value = _resolve_string_tokens(item_value, color_config)

        items.append(
            TreeItem(
                label=label_value,
                icon=icon_value,
                color=color_value,
                asset=asset,
            )
        )

    return items


def _generate_items(parent: TreeItem, path_tokens: list[str], parent_filters: dict | None = None):
    """Generate the list of items that is the result of querying
    MEDM based on the next token in the token list provided.

    Raises:
        RuntimeError
    """
    token = path_tokens.pop(0)
    print('in generate items:', token)
    
    config = QUERY_CONFIG.get(token)
    if config is None:
        raise RuntimeError(f'Invalid query token provided: "{token}".')

    kind = config.get("kind")
    label = config.get("label")
    icon = config.get("icon")

    if kind == "static":
        print('creating static item')
        items = [TreeItem(label=label, icon=icon)]
    elif not config.get("resolution"):
        raise RuntimeError(f'Non-static token "{token}" missing "resolution" configuration.')
    else:
        print('am i here?')
        items = _resolve_items(config, parent, parent_filters)
    
    if len(path_tokens) == 0:
        return items

    forward_filters = config.get("forward_filters") or {}
    next_token = path_tokens[0].strip("{}").lower()
    for item in items:
        print('generate items under:', item.label)
        forward_filter = None
        for ent_type, ent_filters in forward_filters.items():
            if ent_type == next_token:
                forward_filter = {}
                for filter_type, filter_str in ent_filters.items():
                    forward_filter[filter_type] = _resolve_string_tokens(item.asset, filter_str)
        item.children = _generate_items(item, list(path_tokens), forward_filter)
        print('generated', len(item.children), 'items')

    return items


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

    # Create a root tree item representing the project
    project = FlowProject(project_id)
    root = TreeItem(label=f"PROJECT: {project.name}")

    # This list will be modified by the _generate_items() function
    path_tokens = hierarchy_path.split("/")

    # Recursively generate the tree
    items = _generate_items(root, path_tokens)
    root.children = items

    print('hello again?')

    return root
