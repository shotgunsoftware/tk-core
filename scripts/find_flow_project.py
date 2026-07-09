#!/usr/bin/env python3
# Copyright (c) 2026 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY
"""
Standalone CLI to find your Flow project ID using the Flow Data SDK.

Use this script to retrieve the Flow project ID for a given FPT project,
so it can be linked in the FPT site settings.

Usage:
    # Staging environment:
    python scripts/find_flow_project.py --env staging

    # Production environment:
    python scripts/find_flow_project.py --env prod

    # Filter by project name (case-insensitive):
    python scripts/find_flow_project.py --env staging --name "My Project"
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

ENV_CONFIGS = {
    "staging": {
        "auth_application_id": "T9XBK2vAKHSC9kCcQ7yMY3nBXUbm1mAS",
        "auth_base_url": "https://developer-stg.api.autodesk.com/",
        "auth_callback_url": "http://localhost:4201/auth/callback",
        "endpoint": "https://medm-v2.medata-s-ue1.cloudos.autodesk.com/api/v2/graphql",
    },
    "prod": {
        "auth_application_id": "8QyoQKXZ7HDuQFmptJGrzsp2GwpATmyV",
        "auth_base_url": "https://developer.api.autodesk.com/",
        "auth_callback_url": "http://localhost:4201/auth/callback",
        "endpoint": "https://medm-v2.medata-p-ue1.cloudos.autodesk.com/api/v2/graphql",
    },
}


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
        "--env",
        choices=["staging", "prod"],
        required=True,
        help="Target environment: 'staging' or 'prod'",
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

    config = ENV_CONFIGS[args.env]
    print(f"Environment : {args.env}")
    print(f"Endpoint    : {config['endpoint']}")
    print("Authenticating... (browser may open if no valid cached token)")

    auth_config = AuthConfig(
        application_id=config["auth_application_id"],
        base_url=config["auth_base_url"],
        callback_url=config["auth_callback_url"],
        description="Flow find project CLI",
        required_application_scopes=APS_REQUIRED_SCOPES,
        storage_dir=LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
    )
    token = get_access_token(
        auth_config,
        force_reauthentication=args.force_reauth,
        time_out=args.time_out,
    )

    client = GQLClient(
        endpoint=config["endpoint"],
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
