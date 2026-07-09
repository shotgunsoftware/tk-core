#!/usr/bin/env python3
# Copyright (c) 2026 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY
"""
Standalone CLI to find your Flow project ID using the Flow Data SDK.

Use this script to retrieve the Flow project ID for a given FPT project,
so it can be linked in the FPT site settings.

Defaults to production values. Override any individual setting via flags.

Usage:
    # Production (default):
    python scripts/find_flow_project.py

    # Override just the endpoint (e.g. for staging):
    python scripts/find_flow_project.py --endpoint https://medm-v2.medata-s-ue1.cloudos.autodesk.com/api/v2/graphql

    # Override multiple values:
    python scripts/find_flow_project.py --endpoint <url> --application-id <id> --auth-base-url <url>

    # Filter by project name (case-insensitive):
    python scripts/find_flow_project.py --name "My Project"
"""

from __future__ import annotations

import argparse
import os
import sys

# Set up sys.path so tk-core python packages are importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_REPO_ROOT, "python"))

from tank.util import LocalFileStorageManager
from tank_vendor.adsk_auth import AuthConfig, get_access_token
from tank_vendor.flow_data_sdk import GQLClient
from tank_vendor.flow_data_sdk.base import model as flow_model
from tank_vendor.flow_data_sdk.base.client import AuthenticationHandlerBase

APS_REQUIRED_SCOPES = ["data:read", "data:write", "data:create"]

DEFAULT_APPLICATION_ID = "8QyoQKXZ7HDuQFmptJGrzsp2GwpATmyV"
DEFAULT_AUTH_BASE_URL = "https://developer.api.autodesk.com/"
DEFAULT_AUTH_CALLBACK_URL = "http://localhost:4201/auth/callback"
DEFAULT_ENDPOINT = "https://medm-v2.medata-p-ue1.cloudos.autodesk.com/api/v2/graphql"


class TokenAuthHandler(AuthenticationHandlerBase):
    """Auth handler that returns a pre-fetched token."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_authentication_token(self) -> str:
        return self._token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List Flow collections/projects to find project IDs for FPT linking.",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Flow GraphQL endpoint URL (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--application-id",
        default=DEFAULT_APPLICATION_ID,
        help="APS application ID (default: prod value)",
    )
    parser.add_argument(
        "--auth-base-url",
        default=DEFAULT_AUTH_BASE_URL,
        help=f"APS auth base URL (default: {DEFAULT_AUTH_BASE_URL})",
    )
    parser.add_argument(
        "--auth-callback-url",
        default=DEFAULT_AUTH_CALLBACK_URL,
        help=f"OAuth callback URL (default: {DEFAULT_AUTH_CALLBACK_URL})",
    )
    parser.add_argument(
        "--name",
        help="Only show projects whose name contains this string (case-insensitive)",
    )
    parser.add_argument(
        "--force-reauth",
        action="store_true",
        help="Ignore cached tokens and force browser login",
    )
    parser.add_argument(
        "--time-out",
        type=float,
        default=120.0,
        help="Browser auth timeout in seconds (default: 120)",
    )
    args = parser.parse_args()

    print(f"Endpoint    : {args.endpoint}")
    print("Authenticating... (browser may open if no valid cached token)")

    auth_config = AuthConfig(
        application_id=args.application_id,
        base_url=args.auth_base_url,
        callback_url=args.auth_callback_url,
        description="Flow find project CLI",
        required_application_scopes=APS_REQUIRED_SCOPES,
        storage_dir=LocalFileStorageManager.get_global_root(
            LocalFileStorageManager.CACHE
        ),
    )
    token = get_access_token(
        auth_config,
        force_reauthentication=args.force_reauth,
        time_out=args.time_out,
    )

    client = GQLClient(
        endpoint=args.endpoint,
        auth_handler=TokenAuthHandler(token),
    )

    name_filter = (args.name or "").strip().lower()
    collections_resp = client.service_collection.collections(
        flow_model.CollectionsInput()
    ).call()

    collections = getattr(collections_resp, "collections", None) or []
    if not collections:
        print("No collections found for your account.")
        sys.exit(0)

    found_any = False
    for col in collections:
        col_id = getattr(col, "id", None) or ""
        col_name = getattr(col, "name", None) or "(no name)"
        projects_resp = client.service_project.projects_by_collection_id(
            flow_model.ProjectsByCollectionIdInput(collection_id=col_id)
        ).call()
        projects = getattr(projects_resp, "projects", None) or []
        for proj in projects:
            proj_name = getattr(proj, "name", None) or "(no name)"
            proj_id = getattr(proj, "id", None) or ""
            if name_filter and name_filter not in proj_name.lower():
                continue
            if not found_any:
                print("\nCollection -> Project")
                print("-" * 60)
                found_any = True
            print(f"  {col_name} -> {proj_name}")
            print(f"  Project ID: {proj_id}")
            print()
        if not projects and not name_filter:
            print(f"  {col_name} -> (no projects)")

    if not found_any and name_filter:
        print(f"No project matching '{args.name}' found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
