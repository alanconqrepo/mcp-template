from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def _download_blob(connection_string: str, container: str, blob_path: str) -> str:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = client.get_blob_client(container=container, blob=blob_path)
    return blob_client.download_blob().readall().decode("utf-8")


async def get_blob_text(schema: str, object_name: str) -> str:
    """Download the .md metadata file for schema/object_name from Azure Blob Storage."""
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.AZURE_BLOB_CONNECTION_STRING:
        raise ValueError("AZURE_BLOB_CONNECTION_STRING is not configured")

    blob_path = f"{settings.AZURE_BLOB_METADATA_PREFIX}{schema}/{object_name}.md"
    return await asyncio.to_thread(
        _download_blob,
        settings.AZURE_BLOB_CONNECTION_STRING,
        settings.AZURE_BLOB_CONTAINER_NAME,
        blob_path,
    )
