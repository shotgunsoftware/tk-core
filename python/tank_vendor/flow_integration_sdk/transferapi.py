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
API methods for transfering files to the remote server
"""

from __future__ import annotations  # needed for python 3.9 support

import os
import math
import base64
import hashlib
import urllib.request
import urllib.error

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .exceptions import FileUploadError
from .utils import get_logger, trace


@trace
def open_upload_file(client, urn_id: str, upload_uri: str) -> medm_model.UploadFileJob:
    """Open an asynchronous file upload session.

    Creates an upload job on the server for multipart file upload.
    The returned job ID is required for subsequent upload operations.

    Args:
        urn_id: Target blob URN identifier.
        upload_uri: Server-provided upload URI.

    Returns:
        An UploadFileJob instance containing the job ID

    Raises:
        FileUploadError: If the GraphQL API returns an error.
    """
    logger = get_logger(__name__)

    try:
        # Create the open upload file input data
        input_data = medm_model.OpenUploadFileInput(
            upload_uri=upload_uri, urn_id=urn_id
        )
        # Create the open upload file operation and call it
        operation = client.service_binary.open_upload_file(variables=input_data)
        response = operation.call()
        return response.job

    except GQLAPIError as e:
        error_details = f"GraphQL API error (status {e.status_code}): {e.message}"
        logger.error(f"Failed to open upload file session: {error_details}")
        raise FileUploadError(file_path=upload_uri, details=error_details) from e


@trace
def get_upload_file_part(
    client, async_job_id: str, part_num: int, md5_hash: str
) -> medm_model.GetUploadFilePartResponse:
    """Get upload URL for a specific file part

    Retrieves upload information for a specific part of the multipart upload for the single file upload.

    Args:
        async_job_id: The async job ID returned from open_upload_file.
        part_num: The part number to upload (1-based index).
        md5_hash: Base64-encoded MD5 hash of the part data.

    Returns:
        UploadFilePart with upload URL and metadata.

    Raises:
        FileUploadError: If the GraphQL API returns an error.
    """
    logger = get_logger(__name__)

    try:
        # Create the get upload file part input data
        input_data = medm_model.GetUploadFilePartInput(
            async_job_id=async_job_id, hash=md5_hash, part_num=part_num
        )
        # Create the get upload file part operation and call it
        operation = client.service_binary.get_upload_file_part(variables=input_data)
        response = operation.call()
        return response

    except GQLAPIError as e:
        error_details = f"GraphQL API error (status {e.status_code}): {e.message}"
        logger.error(
            f"Failed to get upload file part {part_num} for job {async_job_id}: {error_details}"
        )
        raise FileUploadError(
            file_path=f"job_{async_job_id}_part_{part_num}", details=error_details
        ) from e


@trace
def close_upload_file(
    client, async_job_id: str, state: str, etags: list[str]
) -> medm_model.UploadFileJob:
    """Close the asynchronous file upload session.

    Notifies the server to merge all uploaded parts into the final file.
    Must be called even if the upload failed to clean up server resources.

    Args:
        async_job_id: The async job ID returned from open_upload_file.
        state: Final state of the upload. Must be "SUCCEEDED" or "FAILED".
        etags: List of ETags for each uploaded part.

    Returns:
        An UploadFileJob instance containing the job ID

    Raises:
        ValueError: If an invalid state is provided.
        FileUploadError: If the GraphQL API returns an error.
    """
    logger = get_logger(__name__)

    if state not in ["SUCCEEDED", "FAILED"]:
        raise ValueError(f"Invalid state: {state}.  Must be SUCCEEDED or FAILED")

    try:
        # Create the close upload file input data
        input_data = medm_model.CloseUploadFileInput(
            async_job_id=async_job_id,
            state=state,
            etags=etags,
        )
        # Create the close upload file operation and call it
        operation = client.service_binary.close_upload_file(variables=input_data)
        response = operation.call()
        return response.job

    except GQLAPIError as e:
        error_details = f"GraphQL API error (status {e.status_code}): {e.message}"
        logger.error(
            f"Failed to close upload file session {async_job_id} with state {state}: {error_details}"
        )
        raise FileUploadError(
            file_path=f"job_{async_job_id}", details=error_details
        ) from e


@trace
def upload_blob(client, file_path, urn_id, upload_uri):
    """Upload a file to remote storage using multipart upload.

    Upload workflow:
      1. Opens an upload session and obtains a job ID
      2. Splits the file into chunks and uploads each part
      3. Closes the upload session to finalize

    Args:
        client: The GraphQL client instance
        file_path: The local filename of the file to be uploaded
        urn_id: URN of the blob component to upload to
        upload_uri: URI needed for API transfer
    """
    logger = get_logger(__name__)

    # Create the UploadFileJob
    upload_job = open_upload_file(client=client, urn_id=urn_id, upload_uri=upload_uri)
    async_job_id = upload_job.id
    logger.info(f"Opened upload job: {async_job_id} (state: {upload_job.state})")

    # Keep track of etags
    etags = []

    # Split file into chunks for upload
    total_size = os.path.getsize(file_path)
    part_size = max(5 * 1024 * 1024, math.ceil(total_size / 10000))
    total_parts = math.ceil(total_size / part_size)

    logger.info(f"Uploading {file_path} in {total_parts} chunks of {part_size} bytes")

    upload_state = "SUCCEEDED"

    try:
        with open(file_path, "rb") as f:
            for part_num in range(1, total_parts + 1):
                # Read chunk data
                chunk_data = f.read(part_size)
                md5_hash = base64.b64encode(hashlib.md5(chunk_data).digest()).decode(
                    "utf-8"
                )

                logger.info(f" - Uploading chunk {part_num} : {md5_hash}")

                # Get the upload URL for this part
                part_info = get_upload_file_part(
                    client=client,
                    async_job_id=async_job_id,
                    part_num=part_num,
                    md5_hash=md5_hash,
                )
                upload_url = part_info.send_url

                # Create request and upload the part data
                headers = {
                    "Content-MD5": md5_hash,
                    "Content-Type": "application/octet-stream",
                }
                req = urllib.request.Request(
                    upload_url, data=chunk_data, headers=headers, method="PUT"
                )
                with urllib.request.urlopen(req, timeout=120) as response:
                    if response.status not in (200, 201):
                        raise ValueError(
                            f"Failed to upload part {part_num}: HTTP {response.status}"
                        )
                    etag = response.headers.get("ETag")
                    if not etag:
                        raise ValueError(
                            f"ETag not found in response for part {part_num}"
                        )
                    etags.append(etag)
                logger.info(f"  Part {part_num}/{total_parts} uploaded successfully")

    except Exception as e:
        upload_state = "FAILED"

        raise FileUploadError(file_path=file_path, details=str(e)) from e

    finally:
        # Finally close the file upload job
        close_upload_file(
            client=client,
            async_job_id=async_job_id,
            etags=etags,
            state=upload_state,
        )
