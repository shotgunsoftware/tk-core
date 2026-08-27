"""MEDM URN helpers (parsing and composition)."""

from adsk.flow.local.storage_manager.exceptions import StorageManagerError


def project_id_from_revision_urn(revision_id: str) -> str:
    """Derive a project URN from an asset-revision URN.

    ``urn:medm:assetRevision:<col>:<prj>:<asset>:rev:<n>``
    -> ``urn:medm:project:<col>:<prj>``
    """
    parts = revision_id.split(":")
    if len(parts) < 8 or parts[2] != "assetRevision":
        raise StorageManagerError(f"Cannot derive project URN from malformed revision id: {revision_id!r}")
    return ":".join(["urn", "medm", "project", parts[3], parts[4]])


def compose_revision_urn(asset_id: str, revision_number: int) -> str:
    """Compose an asset-revision URN from an asset URN and a revision number.

    Mirrors mim-core's ``composeAssetRevisionUrn``: the revision URN reuses the
    asset URN's three id segments and appends the numbered suffix, e.g.::

        urn:medm:asset:<col>:<prj>:<asset>
        -> urn:medm:assetRevision:<col>:<prj>:<asset>:rev:<n>
    """
    parts = asset_id.split(":")  # ["urn", "medm", "asset", <col>, <prj>, <asset>]
    if len(parts) < 6 or parts[2] != "asset":
        raise StorageManagerError(f"Cannot compose revision URN from malformed asset id: {asset_id!r}")
    return ":".join(["urn", "medm", "assetRevision", parts[3], parts[4], parts[5], "rev", str(revision_number)])


def compose_version_urn(asset_id: str, version_number: int) -> str:
    """Compose a numbered-version URN from an asset URN and a version number.

    urn:medm:asset:<col>:<prj>:<asset>
    -> urn:medm:assetVersion:<col>:<prj>:<asset>:ver:<n>
    """
    parts = asset_id.split(":")
    if len(parts) < 6 or parts[2] != "asset":
        raise StorageManagerError(f"Cannot compose version URN from malformed asset id: {asset_id!r}")
    return ":".join(["urn", "medm", "assetVersion", parts[3], parts[4], parts[5], "ver", str(version_number)])
