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
This module contains custom object wrappers representing MEDM data.
The object inferface provides a convenient way to access, query and do paginated
iteration of MEDM data.  It also provides an interface to the Flow file storage
solution for seamless access to both the data model and associated binaries.
"""

from __future__ import annotations  # needed for python 3.9 support

import datetime
import re
import urllib
from collections.abc import Iterator
from functools import cache
from typing import Any

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .exceptions import (
    EntityNotFoundError,
    FlowError,
)
from .fetch import (
    download,
    fetch,
    fetch_blob_urls,
    get_thumbnail_file,
    get_thumbnail_url,
)
from .globals import (
    BASE_TYPE_ID,
    BINARY_TYPE_ID,
    COMMENT_TYPE_ID,
    DER_SOURCE_COMP,
    DER_SOURCE_TYPE,
    REFERENCE_TYPE,
    get_client,
    get_webapp_url,
    VARIANT_SET_TYPE,
)
from .sandbox import CheckoutDraftInfo, get_asset_drafts
from .schema import get_schema_id
from .storage import (
    _cache_asset_info,
    get_storage_asset_dir,
    get_storage_component_path,
    get_storage_key,
    get_storage_revision_dir,
)
from .utils import (
    get_logger,
    to_regex_safe_wildcard_string,
    trace,
)


class FlowEntity:
    """Base class with functionality pertinent to MEDM entities.
    This includes Assets and Projects, and basically entails having containership
    capabilities (i.e. having children).
    """

    def __init__(self, entity: medm_model.Asset | medm_model.Project, **kwargs):
        """
        Args:
            entity: The medm entity that this object represents.
        """
        # The medm entity that this class represents
        # This should be a medm_model.Asset or medm_model.Project
        # Storing this object so we can access its properties
        self._entity = entity

        # Query objects - initialized on demand
        # NOTE: In V2 api, query objects should be instantiated every call
        #       and persist the results of that query for the object's lifetime.
        self._q_children: Any = None

        super().__init__(**kwargs)

    @property
    def id(self) -> str:
        """Return MEDM id of entity."""
        return self._entity.id

    @property
    def name(self) -> str:
        """Return MEDM name of entity."""
        return self._entity.name

    @trace
    def iterate_children(self, refresh: bool = False) -> Iterator[FlowAsset]:
        """Query assets contained in this entity.
        Pagination is handled internally within this call via the V2 sdk.
        If this query has already been performed, the cached result will be returned.
        If refresh=True, do a fresh query.

        Raises:
            FlowError
        """
        # Construct new "contains" query if necessary
        if self._q_children is None or refresh:
            client = get_client()
            q_input = medm_model.AssetsByTraversalInput(
                start_at_id=self.id,
                depth=1,
                direction=medm_model.TraverseDirectionEnum.OUTGOING.value,
            )
            self._q_children = client.service_asset.assets_by_traversal(q_input)

        # Wrap existing iterator in V2 sdk
        try:
            for child in self._q_children.assets_iterator:
                # Skip self in the results (traversal API includes start node)
                if child.id == self.id:
                    continue
                yield FlowAsset(child)  # convert to custom Asset object
        except GQLAPIError as exc:
            msg = f'Error querying children of entity "{self.name}". {exc}'
            raise FlowError(msg) from exc

    @trace
    def find_child(self, name: str, force_query: bool = False) -> FlowAsset | None:
        """Find the child that has the given name.

        .. note:: The first match found will be returned.

        Args:
            name: Name to be matched.
            force_query: Force a new query of the asset's children.
                         If False, previous query results will be used if available.

        Returns:
            The FlowAsset entity if found, or None.

        Raises:
            FlowError
        """
        for child in self.iterate_children(refresh=force_query):
            if child.name == name:
                return child
        return None

    @trace
    def find_children(
        self,
        name: str = "",
        type_id: str = "",
        force_query: bool = False,
    ) -> list[FlowAsset]:
        """Return any children that matches the given criteria.

        Args:
            name: Name to be matched. Can support wildcard character '*'.
                  If blank ignore this filter.
            type_id: Match children marked as this type (sub-types will be included).
                     If blank ignore this filter.
            force_query: Force a new query of the asset's children.
                         If False, previous query results will be used if available.
        Returns:
            List of FlowAsset objects.

        Raises:
            FlowError
        """
        matches = []
        regex = "^{}$".format(to_regex_safe_wildcard_string(name))
        for child in self.iterate_children(refresh=force_query):
            if name and not re.match(regex, child.name):
                continue
            if type_id and not child.find_component(type_id=type_id):
                continue
            matches.append(child)
        return matches


class UsesMixin:
    """Mixin class with convenience functionality pertinent to MEDM objects
    that contain "uses" relationships (i.e. dependencies on other MEDM assets).
    This includes FlowAssets and FlowRevisions.
    """

    @trace
    def init_uses(self, version_id: str):
        """Explicit initialization function to store pertinent info.
        This should be called in the __init__() function of any inheriting classes.

        Args:
            version_id: Version id of asset or revision.
        """
        self._uses_version_id = version_id

        # Query objects - initialized on demand
        # NOTE: In V2 api, query objects should be instantiated every call
        #       and persist the results of that query for the object's lifetime.
        self._q_uses: Any = None

    @trace
    def iterate_uses(self, refresh: bool = False) -> Iterator[FlowRevision]:
        """Query uses relationships in this asset/revision.
        Pagination is handled internally within this call via the V2 sdk.
        If this query has already been performed, the cached result will be returned.
        If refresh=True, do a fresh query.

        NOTE: This implementation grabs the entire uses tree because in practice
              this is usually what we need (to fetch dependencies).

        Raises:
            FlowError
        """
        # Construct new "uses" query if necessary
        if self._q_uses is None or refresh:
            client = get_client()
            q_input = medm_model.AssetVersionsByTraversalInput(
                start_at_id=self._uses_version_id,  # type: ignore[attr-defined]
                depth=0,  # retrieve entire tree
                direction=medm_model.TraverseDirectionEnum.OUTGOING.value,
            )
            self._q_uses = client.service_asset.asset_versions_by_traversal(q_input)

        # Wrap existing iterator in V2 sdk
        # NOTE: The iterator function makes the actual query calls so no need to
        #       explicitly invoke call() here.
        try:
            # NOTE: We are getting revisions for now because this is most useful to us
            #       as the primary use case for getting uses information is to fetch
            #       dependencies.
            #
            #       This is fetched through the versions iterator and not the revisions
            #       iterator. Since we are querying outgoing edges, the response gives us
            #       a list of edges like
            #           Rx -> Vy
            #           Rx -> Vz
            #           Rw -> Vu
            #           ...
            #       where R = revision, V = version
            #       The revisions iterator gives us the revision objects associated with
            #       the source of those edges. The versions iterator gives us the version
            #       objects associated with the destination of those edges.
            for ver in self._q_uses.versions_iterator:
                revision = FlowVersion(ver).revision
                yield revision
        except GQLAPIError as exc:
            msg = f"Error querying uses relationships. {exc}"
            raise FlowError(msg) from exc


class ComponentMixin:
    """Mixin class with convenience functionality pertinent to MEDM objects
    that contain components. This includes FlowAssets and FlowRevisions.
    """

    @trace
    def init_components(self, components: list[medm_model.Component]):
        """Explicit initialization function to ingest component data.
        This should be called in the __init__() function of any inheriting classes.

        Args:
            components: List of medm_model.Component objects to be translated and stored
                        as internal Component objects. Must not be None.

        Raises:
            FlowError: If components is None or any component data is invalid.
        """
        if components is None:
            raise FlowError(
                "Components cannot be None. This indicates the query did not "
                "include the components field, or the SDK returned NOT_SET."
            )

        self.components = []  # List of components encoded as custom objects
        for medm_comp in components:
            self.components.append(FlowComponent(self, medm_comp))

    @trace
    def get_binary_components(self) -> list[FlowComponent]:
        """Search for all binary components on asset/revision and return.

        Returns:
            Return a list of Components whose type id inherits from BINARY_TYPE_ID.
            Empty list implies none found.
        """
        type_comps = []
        for comp in self.components:
            if BINARY_TYPE_ID in comp.parent_type_ids:
                type_comps.append(comp)
        return type_comps

    @trace
    def get_type_components(self) -> list[FlowComponent]:
        """Search for all type components on asset/revision and return.

        Returns:
            Return a list of Components whose type id inherits from BASE_TYPE_ID.
            Empty list implies none found.
        """
        type_comps = []
        for comp in self.components:
            if BASE_TYPE_ID in comp.parent_type_ids:
                type_comps.append(comp)
        return type_comps

    @trace
    def get_type_ids(self) -> list[str]:
        """Return the type ids of the given asset/revision.

        Returns:
            Return a list of type ids associated with type components found on asset/revision.
            Empty list implies no types are assigned to asset.
        """
        type_comps = self.get_type_components()
        return [comp.type_id for comp in type_comps]

    @trace
    def get_references(self) -> list[FlowComponent]:
        """Return all reference components on this asset/revision.

        Reference components record dependencies on other MEDM versions at
        publish time (one component per dependency).

        Returns:
            List of FlowComponent objects whose type matches the
            ``component.reference`` schema. Empty list if none found.
        """
        from .schema import get_schema_id

        ref_type_id = get_schema_id(REFERENCE_TYPE)
        return self.find_components(type_id=ref_type_id)

    @trace
    def find_components(
        self,
        name: str = "",
        purpose: str = "",
        type_id: str = "",
    ) -> list[FlowComponent]:
        """Search for component with matching name in given revision.

        ..note:: Filters, if defined, are treated as an intersection, meaning
                 results will conform to all filters.

        Args:
            name: Component name to match. '*' wild card supported.
                  If blank ignore this filter.
            purpose: Match this purpose on component. If blank ignore this filter.
            type_id: Match this type id on component. If blank ignore this filter.

        Returns:
            Component object or None if not found.
        """
        regex = "^{}$".format(to_regex_safe_wildcard_string(name))
        matches = []
        for comp in self.components:
            if name and not re.match(regex, comp.name):
                continue
            if purpose and purpose != comp.purpose:
                continue
            if type_id and type_id not in comp.parent_type_ids:
                continue
            matches.append(comp)
        return matches

    @trace
    def find_component(
        self,
        name: str = "",
        purpose: str = "",
        type_id: str = "",
    ) -> FlowComponent | None:
        """Search for component matching criteria in the same way as described in
        `find_components()`, but return only the first match.

        Args:
            See `find_components()` documentation.

        Returns:
            Component object or None if not found.
        """
        matches = self.find_components(name, purpose, type_id)
        if matches:
            return matches[0]
        return None

    @trace
    def get_sources(self) -> list[str]:
        """Find any Source components within the component list and
        return a list of target versions that they point to.

        NOTE: A source relationship designates provenance. The target
              source cab be considered the entity from which this entity
              was derived.

        Returns:
            List of version ids that this revision designates as a source.

        Raises:
            FlowError
        """
        source_type_id = get_schema_id(DER_SOURCE_TYPE)
        source_comps = self.find_components(type_id=source_type_id)
        try:
            return [c.properties["targetVersion"] for c in source_comps]
        except KeyError as exc:
            msg = f"Malformed source component detected. {exc}"
            raise FlowError(msg) from exc

    @trace
    def get_variant_sets(self) -> dict[str, list[tuple[str, str]]]:
        """Find any VariantSet components within the component list and
        return a dictionary of variant sets of the structure

            set name -> list of variants

        where each variant is a tuple (variant name, asset id).

        Returns:
            Dictionary of variant set names to lists of variants.
        """
        varset_type_id = get_schema_id(VARIANT_SET_TYPE)
        varset_comps = self.find_components(type_id=varset_type_id)
        varsets = {}
        try:
            for comp in varset_comps:
                set_name = comp.properties["setName"]
                variant_name = comp.properties["variantName"]
                variant_id = comp.properties["targetAsset"]
                if set_name not in varsets:
                    varsets[set_name] = []
                varsets[set_name].append((variant_name, variant_id))
        except KeyError as exc:
            msg = f"Malformed variant set component detected. {exc}"
            raise FlowError(msg) from exc
        return varsets


class FlowProject(FlowEntity):
    """Container class for data relevant to a particular medm_model.Project.
    Stores various immutable properties to avoid needing to re-query them.
    Provides functions for obtaining extra data about the medm_model.Project.
    """

    # MEDM entity name
    MEDM_ENTITY = "project"

    @classmethod
    def is_project_id(cls, project_id: str):
        """Return True if given id conforms to expected structure for
        MEDM project ids.
        """
        if not project_id.startswith(f"urn:medm:{cls.MEDM_ENTITY}:"):
            return False  # does not have correct header
        parts = project_id.split(":")
        if len(parts) != 5:
            return False  # does not have correct segments
        return True

    @classmethod
    def get_project_id(cls, input_id: str) -> str:
        """Convert an asset, revision or version id to a project id.

        Args:
            input_id: An MEDM asset, revision or version id.

        Returns:
            An MEDM project id.

        Raises:
            ValueError
        """
        if not FlowAsset.is_asset_id(input_id):
            if not FlowRevision.is_revision_id(input_id):
                if not FlowVersion.is_version_id(input_id):
                    msg = f"Invalid input id provided: {input_id}. "
                    msg += "Input must be an asset, version or revision id."
                    raise FlowError(msg)

        parts = input_id.split(":")
        project_id = f"urn:medm:project:{parts[3]}:{parts[4]}"
        return project_id

    @classmethod
    def get_collection_id(cls, input_id: str) -> str:
        """Return the collection id of the collection session project belongs to.

        Args:
            input_id: An MEDM project, asset, revision or version id.

        Raises:
            FlowError
        """
        try:
            prefix, col_id, sub_id = input_id.rsplit(":", maxsplit=2)
        except ValueError as exc:
            msg = f'Input id "{input_id}" is invalid. {exc}'
            raise FlowError(msg) from exc
        return col_id

    @trace
    def __init__(self, project: str | medm_model.Project):
        """
        Args:
            project: Either an MEDM project id, or an medm_model.Project object.

        Raises:
            EntityNotFoundError
            FlowError
        """
        logger = get_logger(__name__)

        if isinstance(project, str):
            if not self.is_project_id(project):
                msg = f"Invalid project id provided: {project}"
                raise FlowError(msg)
            # Query medm project by id
            client = get_client()
            q_input = medm_model.ProjectsByIdsInput(ids=[project])
            q_project = client.service_project.projects_by_ids(q_input)
            try:
                q_project.call()
            except GQLAPIError as exc:
                msg = f"Error querying project: {project}. {exc}"
                raise FlowError(msg) from exc
            if len(q_project.projects) == 0:
                msg = "Error retrieving MEDM project."
                raise EntityNotFoundError(entity_id=project, details=msg)
            project = q_project.projects[0]
            logger.info(f'Queried project "{project.name}".')
        elif not isinstance(project, medm_model.Project):
            msg = "Project error: input provided is not an medm_model.Project or project id."
            raise FlowError(msg)

        # Trigger Entity class initialization
        super().__init__(project)

    @property
    def collection_id(self) -> str:
        """The id of the collection to which this project belongs."""
        return self.get_collection_id(self.id)

    @property
    def organization_id(self) -> str:
        """Organization id of collection to which project belongs.
        NOTE: This is useful for schema id determination.
        """
        return self._entity.schema_registry_info.organization_id

    @property
    def group_id(self) -> str:
        """Group id of collection to which project belongs.
        NOTE: This is useful for schema id determination.
        """
        return self._entity.schema_registry_info.group_id

    def __str__(self):
        """Readable string representation of project object."""
        s = "------------------------------\n"
        s += f"PROJECT: {self.name}\n"
        s += "------------------------------\n"
        s += f"  id: {self.id}\n"
        s += f"  organization_id: {self.organization_id}\n"
        s += f"  group_id: {self.group_id}\n"
        return s


class FlowAsset(ComponentMixin, UsesMixin, FlowEntity):
    """Container class for data relevant to a particular medm_model.Asset.
    Stores various immutable properties to avoid needing to re-query them.
    Provides functions for obtaining extra data about the medm_model.Asset as well
    as publishing capabilities.
    """

    # MEDM entity nmae
    MEDM_ENTITY = "asset"

    @classmethod
    def is_asset_id(cls, asset_id: str) -> bool:
        """Return True if given id conforms to expected structure for
        MEDM asset ids.
        """
        if not asset_id.startswith(f"urn:medm:{cls.MEDM_ENTITY}:"):
            return False  # does not have correct header
        parts = asset_id.split(":")
        if len(parts) != 6:  # does not have correct segments
            return False
        return True

    @classmethod
    def get_asset_id(cls, input_id: str) -> str:
        """Convert a revision or version id to an asset id.

        Args:
            input_id: An MEDM revision or version id.

        Returns:
            An MEDM asset id.

        Raises:
            ValueError
        """
        if not FlowRevision.is_revision_id(input_id):
            if not FlowVersion.is_version_id(input_id):
                msg = f"Invalid input id provided: {input_id}. "
                msg += "Input must be a version or revision id."
                raise FlowError(msg)

        parts = input_id.split(":")
        asset_id = f"urn:medm:asset:{parts[3]}:{parts[4]}:{parts[5]}"
        return asset_id

    @classmethod
    def get_web_url(cls, asset_id: str):
        """Return url which will open Flow Web App to given asset id.

        ..note:: Please ensure web app base url is configured via
                `globals.set_webapp_url()`.
        """
        webapp_url = get_webapp_url()
        if webapp_url is None:
            raise FlowError("Web app url has not been configured.")
        webapp_url = webapp_url.rstrip("/")
        web_id = urllib.parse.quote(asset_id)
        return f"{webapp_url}/assets?id={web_id}"

    @classmethod
    def get_drafts(cls, asset_id: str) -> list[CheckoutDraftInfo]:
        """Return all local drafts that exist for the given asset.

        .. note:: Currently, we only support a single draft per asset,
                  however this could change in the future with the introduction
                  of multiple checkouts/sandboxes. Returning a list keeps this
                  utility flexible.

        The returned values will be CheckoutDraftInfo objects which will contain
        detailed information about each draft.

        Args:
            asset_id: Id of MEDM asset. This can also be a revision or version id
                      from the same asset.

        Returns:
            List of CheckoutDraftInfo objects.

        Raises:
            FlowError
        """
        # Convert to asset id if necessary
        if FlowRevision.is_revision_id(asset_id) or FlowVersion.is_version_id(asset_id):
            asset_id = FlowAsset.get_asset_id(asset_id)
        elif not FlowAsset.is_asset_id(asset_id):
            msg = f"Invalid input id provided: {asset_id}. "
            msg += "Input must be an asset, revision or version id."
            raise FlowError(msg)
        return get_asset_drafts(asset_id)

    @trace
    def __init__(self, asset: str | medm_model.Asset):
        """
        Args:
            asset: Either an MEDM asset id, or an medm_model.Asset object.

        Raises:
            EntityNotFoundError
            FlowError
        """
        logger = get_logger(__name__)

        if isinstance(asset, str):
            if not self.is_asset_id(asset):
                msg = f"Invalid asset id provided: {asset}"
                raise FlowError(msg)
            client = get_client()
            q_input = medm_model.AssetsByIdsInput(ids=[asset])
            q_asset = client.service_asset.assets_by_ids(q_input)
            try:
                q_asset.call()
            except GQLAPIError as exc:
                msg = f"Error querying asset: {asset}. {exc}"
                raise FlowError(msg) from exc
            if len(q_asset.assets) == 0:
                msg = "Error retrieving MEDM asset."
                raise EntityNotFoundError(entity_id=asset, details=msg)
            asset = q_asset.assets[0]
            logger.info(f'Queried asset "{asset.name}".')
        elif not isinstance(asset, medm_model.Asset):
            msg = "Asset error: input provided is not an medm_model.Asset or asset id."
            raise FlowError(msg)

        # Store general entity information
        super().__init__(asset)
        # Initialize ComponentMixin class
        self.init_components(asset.components)
        # Initialize UsesMixin class
        self.init_uses(asset.numbered_version_id)

        # Cache relevant data about this asset for future use
        _cache_asset_info(self.id)

        # Query objects - initialized on demand
        # NOTE: In V2 api, query objects should be instantiated every call
        #       and persist the results of that query for the object's lifetime.
        self._q_revisions: Any = None
        self._q_versions: Any = None

    @property
    def storage_key(self) -> str:
        """Storage key of asset."""
        return get_storage_key(self.id)

    @property
    def parent_id(self) -> str:
        """MEDM id of parent entity (could be an asset or project)."""
        return self._entity.parent_id

    @property
    def project_id(self) -> str:
        """MEDM id of containing project."""
        return self._entity.project_id

    @property
    def revision_id(self) -> str:
        """Revision id of latest revision of asset at the time of
        object creation or publish.
        """
        return self._entity.revision_id

    @property
    def revision_number(self) -> int:
        """Revision number of latest revision of asset at the time of
        object creation or publish.
        """
        return self._entity.revision_number

    @property
    def version_id(self) -> str:
        """Id of latest (numbered) version of asset at time of
        object creation or publish.
        """
        return self._entity.numbered_version_id

    @property
    def version_number(self) -> int:
        """Number of latest (numbered) version of asset at time of
        object creation or publish.
        """
        return self._entity.version_number

    @property
    def description(self) -> str | None:
        """Description of asset."""
        return self._entity.description

    @property
    def created_at(self) -> datetime.datetime:
        """Creation timestamp of this asset."""
        return datetime.datetime.fromisoformat(
            self._entity.created.date.replace("Z", "+00:00")
        )

    @property
    def created_by(self) -> str | None:
        """Username of creator of this asset."""
        if self._entity.created.user:
            return self._entity.created.user.user_name
        return None

    @property
    @cache
    def type_ids(self) -> list[str]:
        """Return type ids explicitly assigned to asset.
        (This will not include base types.)
        """
        return self.get_type_ids()

    def get_storage_dir(self) -> str:
        """Return the full path of asset directory in primary storage
        (whether or not the directory exists).

        Returns:
            Full path to expected location of primary storage directory on local disk.
        """
        return get_storage_asset_dir(self.id)

    def get_storage_revision_dir(self) -> str:
        """Return the full path of asset directory in primary storage
        for the latest revision of asset (whether or not the directory exists).

        Returns:
            Full path to expected location of primary storage directory on local disk.
        """
        return get_storage_revision_dir(self.id, self.revision_number)

    @trace
    def get_parent(self) -> FlowAsset | FlowProject:
        """Return parent of this asset.

        Raises:
            FlowError
        """
        try:
            if self.parent_id == self.project_id:
                return FlowProject(self.parent_id)
            else:
                return FlowAsset(self.parent_id)
        except FlowError as exc:
            msg = f'Could not retrieve parent for asset "{self.name}".'
            raise FlowError(msg, details=str(exc)) from exc

    @trace
    def get_latest_revision(self) -> FlowRevision:
        """Return an object representing the latest revision of this asset."""
        return FlowRevision.get_revision(self.revision_id)

    @trace
    def iterate_revisions(self, refresh: bool = False) -> Iterator[FlowRevision]:
        """Query revisions of this asset.
        Pagination is handled internally within this call via the V2 sdk.
        If this query has already been performed, the cached result will be returned.
        If refresh=True, do a fresh query.

        Raises:
            FlowError
        """
        # Construct new "revisions" query if necessary
        if self._q_revisions is None or refresh:
            client = get_client()
            q_input = medm_model.AssetRevisionsByAssetIdInput(asset_id=self.id)
            self._q_revisions = (
                client.service_asset_revision.asset_revisions_by_asset_id(q_input)
            )

        # Wrap existing iterator in V2 sdk
        try:
            for rev in self._q_revisions.asset_revisions_iterator:
                revision = FlowRevision(rev)  # convert to custom FlowRevision object
                yield revision
        except GQLAPIError as exc:
            msg = f'Error querying revisions of asset "{self.name}". {exc}'
            raise FlowError(msg) from exc

    @trace
    def iterate_versions(self, refresh: bool = False) -> Iterator[FlowVersion]:
        """Query numbered versions for this asset using V2 GraphQL API.
        Pagination is handled internally within this call via the V2 sdk.
        If this query has already been performed, the cached result will be returned.
        If refresh=True, do a fresh query.

        Only returns NumberedAssetVersion (v1, v2, v3...), not NamedAssetVersion ("latest"),
        since NamedAssetVersion doesn't have direct revision access.

        Args:
            refresh: If True, force a fresh query. If False, use cached results if available.

        Yields:
            AssetVersion objects wrapping NumberedAssetVersion, ordered by version number
            in descending order (newest first: v3, v2, v1).

        Raises:
            FlowError
        """
        # Construct new versions query if necessary
        if self._q_versions is None or refresh:
            client = get_client()
            sort_input = medm_model.SortInput(
                field="created.date", order=medm_model.SortOrderEnum.DESC
            )
            q_input = medm_model.AssetVersionsByAssetIdInput(
                asset_id=self.id, sort=sort_input
            )
            self._q_versions = client.service_asset.asset_versions_by_asset_id(q_input)

        # Wrap existing iterator in V2 sdk
        try:
            for asset_version in self._q_versions.asset_versions_iterator:
                # Skip NamedAssetVersion (like "latest" - they're just pointers)
                if isinstance(asset_version, medm_model.NumberedAssetVersion):
                    yield FlowVersion(asset_version)
        except GQLAPIError as exc:
            msg = f'Error querying versions for asset "{self.name}". {exc}'
            raise FlowError(msg) from exc

    @trace
    def get_derivatives(self) -> list[FlowAsset]:
        """Find siblings of this asset that were derived from it.
        (i.e. have a Source component that points to this asset)

        Raises:
            FlowError
        """

        # This target id should match the beginning of any version id belonging to this asset
        target_id = self.id.replace(self.MEDM_ENTITY, FlowVersion.MEDM_ENTITY)
        der_source_type_id = get_schema_id(DER_SOURCE_TYPE)

        # Generate a query to find assets which contain a Source component with a matching target id
        # Since we know derivative assets will be siblings of the current asset
        # we can safely scope this query to the parent asset with depth of 1.
        client = get_client()
        q_filter = f"has.component.type=={der_source_type_id};"
        q_filter += f"components[typeId:{der_source_type_id}].data.targetVersion.objectId.id=like={target_id}*;"
        q_filter += f"components[typeId:{der_source_type_id}].name=='{DER_SOURCE_COMP}'"
        q_input = medm_model.AssetsByTraversalInput(
            start_at_id=self.parent_id,  # search under parent
            depth=1,  # search immediate children only
            direction=medm_model.TraverseDirectionEnum.OUTGOING.value,
            filters=q_filter,
        )
        q_derivatives = client.service_asset.assets_by_traversal(q_input)

        try:
            q_derivatives.call()
        except GQLAPIError as exc:
            msg = f'Derivative query failed for asset "{self.name}". {exc}'
            raise FlowError(msg) from exc

        # NOTE: the starting asset (i.e. parent) will always be returned in
        #       the asset list, so we must skip that one
        der_assets = [
            FlowAsset(a) for a in q_derivatives.assets if a.id != self.parent_id
        ]
        return der_assets

    @trace
    def find_derivative(
        self,
        target_type_id: str,
    ) -> FlowAsset | None:
        """Search asset to find an outbound derivative where the target
        matches the criteria provided.

        Args:
            target_type_id: Type of target revision.

        Returns:
            The first derivative asset found, or None.
        """
        # Get list of assets that are derivatives of this asset
        der_assets = self.get_derivatives()
        # Now filter out derivatives of the wrong type
        der_assets = [a for a in der_assets if target_type_id in a.type_ids]

        if len(der_assets) > 0:
            return der_assets[0]

        return None

    def __str__(self):
        """Readable string representation of asset object."""
        s = "------------------------------\n"
        s += f"ASSET: {self.name}\n"
        s += "------------------------------\n"
        s += f"  id: {self.id}\n"
        s += f"  storage_key: {self.storage_key}\n"
        s += f"  version: {self.version_number}\n"
        s += f"  revision: {self.revision_number}\n"
        s += f"  type_ids: {self.type_ids}\n"
        return s


class FlowRevision(ComponentMixin, UsesMixin):
    """Container class for data relevant to a particular medm_model.AssetRevision.
    Stores various immutable properties to avoid needing to re-query them.
    Since revisions are by definition immutable, this class stores a cache
    of all previously accessed revisions so that they are never queried more than once.
    """

    # MEDM entity name
    MEDM_ENTITY = "assetRevision"

    # Dictionaries that track already accessed revisions for reuse
    # key = revision ids, value = FlowRevision object
    _revision_cache: dict[str, FlowRevision] = {}

    @classmethod
    def is_revision_id(cls, revision_id: str) -> bool:
        """Return True if given id conforms to expected structure for
        MEDM revision ids.
        """
        if not revision_id.startswith(f"urn:medm:{cls.MEDM_ENTITY}:"):
            return False  # does not have correct header
        parts = revision_id.split(":")
        if len(parts) != 8:
            return False  # does not have correct segments
        if parts[-2] != "rev":
            return False  # does not fit revision format
        try:
            int(parts[-1])
        except ValueError:
            return False  # does not have a valid revision number
        return True

    @classmethod
    def get_revision_id(cls, asset_id: str, revision_number: int) -> str:
        """Generate a revision id based on inputs.
        NOTE: resultant revision id will be structurally valid, but
        may not actually exist.

        Args:
            asset_id: MEDM asset id.
            revision_number: Number of revision within asset.

        Returns:
            MEDM revision id.
        """
        if not FlowAsset.is_asset_id(asset_id):
            raise FlowError(f"Invalid asset id provided: {asset_id}")

        # Remove asset header in id
        asset_id = asset_id.split(":", maxsplit=3)[-1]

        return f"urn:medm:{cls.MEDM_ENTITY}:{asset_id}:rev:{revision_number}"

    @classmethod
    def get_revision_number(cls, revision_id: str) -> int:
        """Return revision number based on id."""
        if not cls.is_revision_id(revision_id):
            raise FlowError(f"Invalid revision id provided: {revision_id}")
        # NOTE: since id passed validation, there should be no errors here
        return int(revision_id.split(":")[-1])

    @classmethod
    def get_revision(cls, revision: str | medm_model.AssetRevision) -> FlowRevision:
        """Retrieve a cached FlowRevision object based on provided revision id
        or create a new FlowRevision object to represent the revision.

        Args:
            revision: Either a string medm revision id, or a medm_model.AssetRevision object.

        Returns:
            FlowRevision object.

        Raises:
            EntityNotFoundError
            FlowError
        """
        if isinstance(revision, medm_model.AssetRevision):
            revision_id = revision.id
        else:
            revision_id = revision

        # Return cached value if available
        if revision_id in cls._revision_cache:
            return cls._revision_cache[revision_id]

        # Convert to custom object
        return FlowRevision(revision)

    @trace
    def __init__(self, revision: str | medm_model.AssetRevision):
        """
        Args:
            revision: Either an MEDM revision id, or an medm_model.AssetRevision object.

        Raises:
            EntityNotFoundError
            FlowError
        """
        logger = get_logger(__name__)

        if isinstance(revision, str):
            if not self.is_revision_id(revision):
                msg = f"Invalid revision id provided: {revision}"
                raise FlowError(msg)
            client = get_client()
            q_input = medm_model.AssetRevisionsByIdsInput(ids=[revision])
            q_revision = client.service_asset_revision.asset_revisions_by_ids(q_input)
            try:
                q_revision.call()
            except GQLAPIError as exc:
                msg = f"Error querying revision: {revision}. {exc}"
                raise FlowError(msg) from exc
            if len(q_revision.revisions) == 0:
                msg = "Error retrieving MEDM revision."
                raise EntityNotFoundError(entity_id=revision, details=msg)
            revision = q_revision.revisions[0]
            msg = f'Queried revision "{revision.name}" revision number {revision.revision_number}.'
            logger.info(msg)
        elif not isinstance(revision, medm_model.AssetRevision):
            msg = "Revision error: input provided is not an medm_model.AssetRevision or revision id."
            raise FlowError(msg)

        # The medm revision that this class represents
        # This should be a medm_model.AssetRevision
        # Storing this object so we can access its properties as needed
        self._revision = revision

        # Initialize ComponentMixin class
        self.init_components(revision.components)
        # Initialize UsesMixin class
        self.init_uses(revision.numbered_version_id)

        # Cache object
        # Revisions are immutable so we should only ever query each revision once!
        FlowRevision._revision_cache[revision.id] = self

    # --------------------------------------------------------------------
    # Enforce read-only properties on revision objects since these objects
    # are cached and should be considered immutable.
    # --------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._revision.id

    @property
    def asset_id(self) -> str:
        """Return asset id of revision."""
        return self._revision.asset_id

    @property
    def name(self) -> str:
        return self._revision.name

    @property
    def revision_number(self) -> int:
        """Number of this revision.
        This value is strictly acsending per revision and begins at 1.
        """
        return self._revision.revision_number

    @property
    def version_id(self) -> str:
        """Return id of "numbered version" to which this revision belongs.
        NOTE: Multiple revisions may map to the same numbered version.
              The current revision may or may not be the latest of that set.
        """
        return self._revision.numbered_version_id

    @property
    def version_number(self) -> int:
        """Return version number to which this revision belongs.
        Version numbers with respect to revisions are non-decreasing, however,
        multiple successive revisions may have the same version number.
        This value increments beginning at 1.
        """
        return self._revision.version_number

    @property
    def storage_key(self) -> str:
        """Storage key is the asset identifier portion of the full asset id."""
        return get_storage_key(self.asset_id)

    @property
    def comment(self) -> str | None:
        """Return the publish comment stored in a comment component if it exists."""
        comment_comp = self.find_component(type_id=COMMENT_TYPE_ID)
        if comment_comp:
            # Will ignore malformed comment components for now
            return comment_comp.properties.get("subjectLine")
        return None

    def get_storage_dir(self) -> str:
        """Return the full path of asset revision directory in primary storage
        (whether or not the directory exists).

        Returns:
            Full path to expected location of cached storage directory on local disk.
        """
        return get_storage_revision_dir(self.asset_id, self.revision_number)

    def get_storage_component_path(
        self,
        component_name: str = "",
        component_purpose: str = "",
        blob_index: int = 0,
    ) -> str | None:
        """Return the full path of the component blob file of the given asset revision
        in primary storage (whether or not the file exists).

        Args:
            component_name: If provided, search for component with this name and return its storage path.
                            This should be unique within the revision.
            component_purpose: If provided, search for a component with this purpose and return
                               its storage path. There may be multiple components with the same purpose,
                               so the first match will be returned.
            blob_index: Specific blob from source component to get.

        ..note:: If both component name and purpose are provided, the first intersection
                 of both criteria will be returned.

        Returns:
            Full path to expected location of cached source file on local disk, or
            None if the component does not exist on the revision.
        """
        return get_storage_component_path(
            self._revision,
            component_name=component_name,
            component_purpose=component_purpose,
            blob_index=blob_index,
        )

    @trace
    def fetch(self, component_purpose: str, fetch_dependencies: bool = False):
        """Fetch the given component of this revision if not already on disk.
        If the specified component does not exist, nothing will happen.

        Args:
            component_purpose: Fetch component of this purpose.
            fetch_dependencies: If True, also fetch components of the same purpose
                                in this revisions "uses" tree.
                                (This may not be appropriate for all component purposes.)
        """
        fetch(
            self._revision,
            component_purpose=component_purpose,
            fetch_dependencies=fetch_dependencies,
        )

    @trace
    def get_thumbnail_file(self) -> str:
        """Return the file path to the revision's thumbnail if it exists,
        fetching it if necessary.

        Returns:
            Full path to thumbnail in storage.

        Raises:
            ThumbnailError
        """
        return get_thumbnail_file(self._revision)

    @trace
    def get_thumbnail_url(self) -> str:
        """Return the signed url to the revision's thumbnail if it exists.

        Returns:
            Url that can be used to download thumbnail.

        Raises:
            ThumbnailError
        """
        return get_thumbnail_url(self._revision)

    def __str__(self):
        """Readable string representation of revision object."""
        s = "------------------------------\n"
        s += f"REVISION: {self.name} - r{self.revision_number}\n"
        s += "------------------------------\n"
        s += f"  id: {self.id}\n"
        s += f"  storage_key: {self.storage_key}\n"
        s += f"  version: {self.version_number}\n"
        return s


class FlowVersion:
    """Container class for data relevant to a medm_model.NumberedAssetVersion."""

    # MEDM entity name
    MEDM_ENTITY = "assetVersion"

    @classmethod
    def is_version_id(cls, version_id: str) -> bool:
        """Return True if given id conforms to expected structure for
        MEDM version ids.
        """
        if not version_id.startswith(f"urn:medm:{cls.MEDM_ENTITY}:"):
            return False  # does not have correct header
        parts = version_id.split(":")
        if len(parts) != 8:
            return False  # does not have correct segments
        if parts[-2] != "ver":
            return False  # does not follow version format
        # NOTE: ignoring "named" versions for now
        try:
            int(parts[-1])
        except ValueError:
            return False  # does not have a valid version number
        return True

    @classmethod
    def get_version_number(cls, version_id: str) -> int:
        """Return version number based on id."""
        if not cls.is_version_id(version_id):
            raise FlowError(f"Invalid version id provided: {version_id}")
        # NOTE: since id passed validation, there should be no errors here
        return int(version_id.split(":")[-1])

    @classmethod
    def get_version_id(cls, asset_id: str, version_number: int) -> str:
        """Generate a version id based on inputs.
        NOTE: resultant version id will be structurally valid, but
        may not actually exist.

        Args:
            asset_id: MEDM asset id.
            version_number: Number of version within asset.

        Returns:
            MEDM version id.
        """
        if not FlowAsset.is_asset_id(asset_id):
            raise FlowError(f"Invalid asset id provided: {asset_id}")

        # Remove asset header in id
        asset_id = asset_id.split(":", maxsplit=3)[-1]

        return f"urn:medm:{cls.MEDM_ENTITY}:{asset_id}:ver:{version_number}"

    @trace
    def __init__(self, version: str | medm_model.NumberedAssetVersion):
        """
        Args:
            version: Either an MEDM version id, or an medm_model.NumberedAssetVersion object.

        Raises:
            EntityNotFoundError
            FlowError
        """
        logger = get_logger(__name__)

        if isinstance(version, str):
            if not self.is_version_id(version):
                msg = f"Invalid version id provided: {version}"
                raise FlowError(msg)
            client = get_client()
            q_input = medm_model.AssetVersionsByIdsInput(ids=[version])
            q_version = client.service_asset.asset_versions_by_ids(q_input)
            try:
                q_version.call()
            except GQLAPIError as exc:
                msg = f"Error querying version: {version}. {exc}"
                raise FlowError(msg) from exc
            if len(q_version.versions) == 0:
                msg = "Error retrieving MEDM version."
                raise EntityNotFoundError(entity_id=version, details=msg)
            version = q_version.versions[0]
            msg = f"Queried version number {version.version_number}."
            logger.info(msg)
        elif not isinstance(version, medm_model.NumberedAssetVersion):
            msg = "Version error: input provided is not an medm_model.NumberedAssetVersion or version id."
            raise FlowError(msg)

        # The medm version that this class represents
        # This should be a medm_model.NumberedAssetVersion
        # Storing this object so we can access its properties as needed
        self._version = version

        # Numbered versions have attached revision objects
        # Take the opportunity to cache this since revisions are immutable
        # and should only be queried once!
        FlowRevision._revision_cache[self.revision.id] = self.revision

    @property
    def id(self) -> str:
        return self._version.id

    @property
    def asset_id(self) -> str:
        """Return asset id of version."""
        return self._version.asset_id

    @property
    def version_number(self) -> int:
        """Return number of version."""
        return self._version.version_number

    @property
    def revision(self) -> FlowRevision:
        """Return current revision associated with version.
        The revision associated with a version can change over time.
        The version object would need to be re-queried to see the changes.
        """
        return FlowRevision(self._version.revision)

    @property
    def created_at(self) -> datetime.datetime:
        """Creation timestamp of this version."""
        return datetime.datetime.fromisoformat(
            self._version.created.date.replace("Z", "+00:00")
        )

    @property
    def created_by(self) -> str | None:
        """Username of creator of this version."""
        if self._version.created.user:
            return self._version.created.user.user_name
        return None

    def __str__(self):
        """Readable string representation of version object."""
        s = "------------------------------\n"
        s += f"VERSION: v{self.version_number}\n"
        s += "------------------------------\n"
        s += f"  id: {self.id}\n"
        s += f"  revision: {self.revision.name} (r{self.revision.revision_number})\n"
        return s


class FlowComponent:
    """Container class for data relevant to a particular medm_model.Component.
    Presents component data in a more readable and accessible way.
    """

    @trace
    def __init__(self, revision: FlowRevision, component: medm_model.Component):
        """
        Args:
            revision: Parent FlowRevision object.
            component: Medm component object to convert to custom object.

        Raises:
            FlowError
        """
        # FlowRevision object that this component belongs to
        self.revision = revision
        # Original MEDM component object
        self._component = component
        # Uniquely identifying component name
        self.name = component.name
        # Type id specifies the type of the component (e.g. binary, type, etc)
        self.type_id = component.type_id
        # Ancestors of type id
        self.parent_type_ids = component.parent_type_ids
        # The purpose further specifies what kind of component this is
        # For instance two binary components can have different purposes
        self.purpose = component.data.get("purpose", "")
        # For binary components, the blob array specifies the files associated
        # with the component
        self.blobs = []
        # Arbitrary additional properties stored on the component
        self.properties = {}  # key = property name, value = property value

        blob_data = component.data.get("data", [])
        for blob in blob_data:
            self.blobs.append(Blob(blob))

        for prop, val in component.data.items():
            if prop in ["data", "purpose"]:
                continue  # already processed these
            if isinstance(val, dict) and "reference" in val["typeid"]:
                try:
                    # For reference typed properties, store the target entity id
                    # as the property value
                    self.properties[prop] = val["objectId"]["id"]
                except KeyError:
                    # Ignore malformed properties
                    continue
            else:
                self.properties[prop] = val

    @trace
    def get_blob_path(self, blob_index: int = 0) -> str:
        """Return the relative path stored on the blob at the given index
        of the given component.

        Args:
            blob_index: The index into the blob array to be inspected.

        Returns:
            The path of the blob relative to the asset revision folder.

        Raises:
            FlowError
        """
        if len(self.blobs) <= blob_index:
            msg = f'Component "{self.name}" does not have a blob at index {blob_index}.'
            raise FlowError(msg)
        return self.blobs[blob_index].path

    @trace
    def fetch_blob_urls(self) -> list[str]:
        """Query list of urls for component blobs that can be used for
        downloading. Order should be preserved.

        Raises:
            FlowError
        """
        # Get the URNs that we need to fetch
        urns = [blob.uri for blob in self.blobs]

        # Get info about current project
        project_id = FlowProject.get_project_id(self.revision.id)

        return fetch_blob_urls(project_id, urns)

    @trace
    def download(
        self,
        directory: str,
        file_sequence: bool = False,
        skip_download: bool = False,
    ) -> dict[int, str]:
        """Download all binary blobs in component to given directory.
        Directory must exist, and component must be a binary component.

        Args:
            directory: Existing folder location to be downloaded to.
            file_sequence: If True, expect the component to contain a
                           zipped file sequence, and automatically expand it.
            skip_download: Only relevant for file sequences. Used when
                           the source zip file has already been downloaded, but
                           the files haven't been extracted.

        Returns:
            Dictionary of blob index to full path of downloaded file.

        Raises:
            FlowError
        """
        # Get info about current project
        project_id = FlowProject.get_project_id(self.revision.id)

        # Do download
        return download(
            self._component,
            project_id,
            directory,
            file_sequence,
            skip_download,
        )

    def __str__(self):
        """Readable string representation of component object."""
        s = "------------------------------\n"
        s += f"COMPONENT: {self.name}\n"
        s += "------------------------------\n"
        s += f"  type_id: {self.type_id}\n"
        if self.purpose:
            s += f"  purpose: {self.purpose}\n"
        return s


class Blob:
    """Container class for data relevant to a blob within a component."""

    @trace
    def __init__(self, blob_data: dict):
        """
        Args:
            blob_data: A dictionary of blob information from an medm component.

        Raises:
            FlowError
        """
        try:
            self.path = blob_data["path"]
            self.uri = blob_data["uri"]
        except KeyError as exc:
            msg = "Invalid blob data dictionary provided."
            raise FlowError(msg, details=str(exc)) from exc

    def __str__(self):
        """Readable string representation of blob object."""
        return f"[BLOB: {self.path}]"
