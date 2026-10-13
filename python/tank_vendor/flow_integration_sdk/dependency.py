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
This module contains convenience classes/utilities for dealing with
file dependencies within an asset.
"""
from __future__ import annotations  # needed for python 3.9 support

import json
import re
from dataclasses import dataclass, field, fields
from enum import Enum

from tank_vendor.flow_integration_sdk.exceptions import FlowError
from tank_vendor.flow_integration_sdk.storage import storage_key_to_asset_id
from tank_vendor.flow_integration_sdk.objects import (
    FlowRevision,
    FlowVersion,
)
from tank_vendor.flow_integration_sdk.utils import (
    cleanpath,
    to_regex_safe_wildcard_string,
    trace,
)


class DepType(Enum):
    """Enum of dependency data types."""

    #: Link to another asset in Flow.
    ASSET = "asset"
    #: Link to a file external to Flow, or packaged within current asset.
    LOCAL = "local"
    #: No specific type.
    NONE = ""
    #: Link to the main scene file of the current asset.
    ROOT = "root"


@dataclass
class DependencyData:
    """Store data relevant to an dependency within a scene.

    General Properties:

        - dep_type: General type of dependency. See :class:`.DepType` enum for valid values.
        - node_handle: Unique identifier to the node with the dependency.
        - node_type: Type name of node (specific type of dependency).
        - attribute: Name of attribute which stores the file path (not always applicable).
        - file_path: Absolute file path of dependency.
        - raw_path: Raw file path stored in scene.
        - dependencies: List of nested dependencies within the file designated by file_path.

    Asset Properties: (pertinent to asset type dependencies only)

        - asset_id: Asset entity id.
        - version: Version of revision.
        - revision_id: Revision id.
        - component_name: Unique component identifier within revision.
        - blob_index: Index into blob array of component.
    """

    # General properties

    dep_type: DepType = DepType.NONE
    node_handle: str = ""
    node_type: str = ""
    attribute: str = ""
    file_path: str = ""
    raw_path: str = ""
    parent: DependencyData | None = None
    dependencies: list[DependencyData] = field(default_factory=lambda: [])

    # Asset properties
    asset_id: str = ""
    revision_id: str = ""
    version_id: str = ""
    component_name: str = ""
    blob_index: int = 0

    def identify_component(self):
        """Determine asset component identification based on file path.
        If provided, copy info from cached dependency tree to avoid querying it.
        """
        # Parse file path for asset info
        comp_info = identify_component(self.file_path)
        if comp_info:
            self.asset_id = comp_info.get("asset_id")
            self.revision_id = comp_info.get("revision_id")
            self.version_id = comp_info.get("version_id")
            self.component_name = comp_info.get("component_name")
            self.blob_index = comp_info.get("blob_index")

    @property
    def revision_num(self):
        """Return number of revision based on revision id."""
        return FlowRevision.get_revision_number(self.revision_id)

    @property
    def version_num(self):
        """Return number of version based on version id."""
        return FlowVersion.get_version_number(self.version_id)

    def set_type(self):
        """Set dependency type based on current properties."""
        # Can assume any dependency with asset information is an asset dependency
        self.dep_type = DepType.ASSET if self.asset_id else DepType.LOCAL

    def flatten_dependencies(self):
        """Create flat list of all dependencies in tree."""
        deps = [self]
        for dep in self.dependencies:
            deps.extend(dep.flatten_dependencies())
        return deps

    def get_external_dependencies(self, top_level: bool = True) -> list[DependencyData]:
        """Return list of external dependency objects.

        .. note:: external dependencies of internal dependencies will be ignored
              because they are not considered external to the current asset context.

        Args:
            top_level: If True, only return external dependencies in immediate
                       dependency list.  Otherwise, include sub dependencies too.

        Returns
            List of DependencyData objects of type DepType.LOCAL.
        """
        ext_deps = []
        for dep in self.dependencies:
            if dep.dep_type == DepType.LOCAL:
                ext_deps.append(dep)
            if not top_level and dep.dep_type != DepType.ASSET:
                ext_deps.extend(dep.get_external_dependencies(top_level=False))
        return ext_deps

    def get_internal_dependencies(self, top_level: bool = True) -> list[DependencyData]:
        """Return list of internal dependency objects.

        Args:
            top_level: If True, only return internal dependencies in immediate
                       dependency list.  Otherwise, include all sub dependencies too.

        Returns:
            List of DependencyData objects of type DepType.ASSET.
        """
        int_deps = []
        for dep in self.dependencies:
            # In searching for internal dependencies, we must also include those
            # that are referenced by external dependencies because they also
            # need to be "registered" as internal references of current asset.
            #
            # If only getting top level internal references, do not search sub
            # dependencies once an internal dependency is found, but must continue
            # to search sub dependencies of external dependencies in case an internal
            # reference exists within.
            if dep.dep_type == DepType.ASSET:
                int_deps.append(dep)
                if top_level:
                    continue
            int_deps.extend(dep.get_internal_dependencies(top_level=top_level))

        return int_deps

    def find(
        self,
        node_handle: str | None = None,
        file_path: str | None = None,
        node_type: str | None = None,
    ) -> list[DependencyData]:
        """Find node within dependency tree.

        Note: multiple criteria acts as a union, not an intersection.

        Args:
            node_handle: If provided, match dependency node with this handle.
                         Wildcard character '*' is supported.
                         This criteria will be given precedence.
            file_path: If provided, match by file path.
                       Wildcard character '*' is supported.
                       This criteria has second priority.
            node_type: If provided, match by node type.
                       Wildcard character '*' is supported.
                       This criteria has third priority.

        Returns:
            List of DepedencyData nodes that match to ANY of given criteria.
        """
        matches = []
        matched_self = False
        if node_handle is not None:
            expression = f"^{to_regex_safe_wildcard_string(node_handle)}$"
            if re.match(expression, self.node_handle):
                matches.append(self)
                matched_self = True
        if not matched_self and file_path is not None:
            expression = f"{to_regex_safe_wildcard_string(file_path.lower())}$"
            if re.match(expression, self.file_path.lower()):
                matches.append(self)
                matched_self = True
        if not matched_self and node_type is not None:
            expression = f"{to_regex_safe_wildcard_string(node_type)}$"
            if re.match(expression, self.node_type):
                matches.append(self)
        for dep in self.dependencies:
            result = dep.find(node_handle, file_path, node_type)
            matches.extend(result)

        return matches

    def contains(self, dep: DependencyData) -> DependencyData | None:
        """Check tree for equivalent dependency node and return."""
        deps = self.flatten_dependencies()
        for d in deps:
            if d == dep:
                return d
        return None

    def match(self, dep: DependencyData) -> DependencyData | None:
        """Find matching dependency node in tree.

        A match entails that the following properties are the same:
            * node_handle
            * node_type
            * attribute
            * asset_id
            * component_name

        Args:
            dep: The dependency data to be matched.

        Returns:
            First node in the tree that fits matching criteria, or None if not found.
        """
        deps = self.flatten_dependencies()
        for d in deps:
            if d.node_handle != dep.node_handle:
                continue
            elif d.node_type != dep.node_type:
                continue
            elif d.attribute != dep.attribute:
                continue
            elif d.asset_id != dep.asset_id:
                continue
            elif d.component_name != dep.component_name:
                continue
            return d
        return None

    def __lt__(self, other: DependencyData) -> bool:
        """Implement less-than comparison operator to make objects sortable."""
        return self.node_handle < other.node_handle

    def __eq__(self, other: DependencyData) -> bool:
        """Implement equals operator."""
        if (
            self.node_handle == other.node_handle
            and self.node_type == other.node_type
            and self.attribute == other.attribute
            and self.file_path == other.file_path
        ):
            return True
        return False

    def asdict(self):
        """Convert object to dictionary."""
        # NOTE: using default asdict() function causes infinite recursion

        # Convert basic properties
        result = {}
        for f in fields(self):
            if f.name in ["dependencies", "parent"]:
                continue
            result[f.name] = getattr(self, f.name)

        # Convert dependency list recursively
        result["dependencies"] = [dep.asdict() for dep in self.dependencies]

        # Convert dep_type to string
        result["dep_type"] = self.dep_type.value

        return result

    def pprint(self, index: int = 0, tabs: int = 0, recursive=True):
        """Print dependency tree in a readable way."""
        print("\t" * tabs + "-----------------------------------------")
        print("\t" * tabs + f"{index} - {self.dep_type.name}")
        print("\t" * tabs + "-----------------------------------------")

        asset_props = [
            "asset_id",
            "version",
            "revision_id",
            "component_name",
            "blob_index",
        ]

        for prop, value in self.__dict__.items():
            if prop in ["dependencies", "dep_type"]:
                continue
            elif prop == "parent":
                if value is not None:
                    print("\t" * tabs + f"{prop}: {value.node_handle}")
                continue
            elif prop in asset_props and self.dep_type is not DepType.ASSET:
                continue
            print("\t" * tabs + f"{prop}: {str(value)}")

        if recursive and self.dependencies:
            print(" ")
            print("\t" * tabs + "Sub-dependencies:")
            for i, dep in enumerate(self.dependencies):
                dep.pprint(i, tabs + 1)

    @classmethod
    def convert(cls, dep_json: dict | str) -> DependencyData:
        """Convert a json representation of a dependency tree into object representation.

        Args:
            dep_json: Json in dictionary or string format.

        Returns:
            Root of dependency tree.

        Raises:
            ValueError: If dep_json is a string that cannot be parsed as JSON.
        """
        # Convert json string to dictionary
        if isinstance(dep_json, str):
            try:
                dep_json = json.loads(dep_json)
            except Exception as exc:  # pylint: disable=broad-except
                raise ValueError("Invalid json provided.") from exc

        dep = DependencyData(**dep_json)  # type: ignore[arg-type]

        try:
            # dep type is assumed to be a string, convert back to enum value
            dep.dep_type = DepType(dep.dep_type)
        except Exception:
            dep.dep_type = DepType.NONE

        # Properly convert sub-dependencies to objects
        subdeps = []
        for d in dep.dependencies:
            subdeps.append(DependencyData.convert(d))  # type: ignore[arg-type]
        dep.dependencies = subdeps
        for d in subdeps:
            d.parent = dep

        return dep


@trace
def identify_component(file_path: str) -> dict | None:
    """Given a file path, determine if it belongs to an asset, and
    return information identifying the exact component blob that the path
    is associated with.

    NOTE: Only paths within primary storage (NFS cache) can be identified.
    All other paths, including sandbox paths, will return None.

    Args:
        file_path: Absolute path to a file.
        ignore_root: If True, root directory does not need to map to
                     current configured roots. It is recommended to keep
                     this to True if not trying validate full path for optimal
                     performance.

    Returns:
        Dictionary with keys:
            * asset_id -> Id of asset
            * revision_id -> Id of revision
            * version_id -> Id of version
            * component_name -> Name of component
            * blob_index -> Index into binary array of component

        or None if the file path cannot be identified.
    """
    file_path = cleanpath(file_path)

    # Absolute path pattern (expecting a root)
    expr = r".*(?P<comp_path>/[^/]+/((r\d+)|(draft))/.+)"
    m = re.match(expr, file_path)
    if not m:
        # Relative path pattern (expecting to begin with storage id)
        expr = r"(?P<comp_path>[^/]+/((r\d+)|(draft))/.+)"
        m = re.match(expr, file_path)
        if not m:
            # Not an asset path - failed test for overall asset path pattern
            return None
    comp_path = m.group("comp_path")

    # add prepended / to match expected asset path pattern if not present
    if not comp_path.startswith("/"):
        comp_path = "/" + comp_path

    # Parse expected pieces of asset path
    try:
        _, storage_id, rev_num, comp_path = comp_path.split("/", maxsplit=3)
    except ValueError:
        # Not an asset path - unable to parse into key path components
        return None

    # Look up asset based on storage key
    try:
        asset_id = storage_key_to_asset_id(storage_id)
    except FlowError:
        # Not an asset path - storage key component does not map to an asset
        return None

    # Convert revision number to integer
    if rev_num == "draft":
        # Not an asset path - draft paths don't count
        return None
    else:
        try:
            rev_num = int(rev_num.strip("r"))
        except ValueError:
            # Not an asset path - non-int value for revision number component
            return None

    revision_id = FlowRevision.get_revision_id(asset_id, rev_num)
    try:
        # NOTE: Using accessor method rather than constructing new instance
        #       because this will return a cached object if it exists
        #       This is ok since revisions are immutable.
        revision = FlowRevision.get_revision(revision_id)
    except FlowError:
        # Not an asset - revision number is out of range
        return None

    # Determine component and blob index based on component path
    # Try and match against existing binary components on revision
    component = blob_index = None
    bin_comps = revision.get_binary_components()
    if "%" in comp_path:
        # File sequence paths will be stored as a zip file
        comp_path, _, _ = comp_path.rsplit(".", maxsplit=2)
        comp_path += ".zip"
    for comp in bin_comps:
        for i, blob in enumerate(comp.blobs):
            if blob.path == comp_path:
                component = comp
                blob_index = i
                break
    if component is None:
        # Not an asset path - no component blob matches file
        return None

    return {
        "asset_id": asset_id,
        "revision_id": revision_id,
        "version_id": revision.version_id,
        "component_name": component.name,
        "blob_index": blob_index,
    }
