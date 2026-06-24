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


# ── Binary helpers ────────────────────────────────────────────────────────────


def _upload_blob_bytes(connection_string: str, container: str, blob_path: str, data: bytes) -> None:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = client.get_blob_client(container=container, blob=blob_path)
    blob_client.upload_blob(data, overwrite=True)


def _download_blob_bytes(connection_string: str, container: str, blob_path: str) -> bytes:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = client.get_blob_client(container=container, blob=blob_path)
    return blob_client.download_blob().readall()


def _generate_blob_sas_url(
    connection_string: str, container: str, blob_path: str, expiry_hours: int
) -> str:
    from datetime import UTC, datetime, timedelta

    from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

    service_client = BlobServiceClient.from_connection_string(connection_string)
    account_name = service_client.account_name
    account_key = service_client.credential.account_key
    expiry = datetime.now(UTC) + timedelta(hours=expiry_hours)
    token = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_path,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
    )
    return f"https://{account_name}.blob.core.windows.net/{container}/{blob_path}?{token}"


def _get_connection_string() -> str:
    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.AZURE_BLOB_CONNECTION_STRING:
        raise ValueError("AZURE_BLOB_CONNECTION_STRING is not configured")
    return settings.AZURE_BLOB_CONNECTION_STRING


async def upload_blob_bytes(container: str, blob_path: str, data: bytes) -> None:
    """Upload binary content to Azure Blob Storage."""
    conn = _get_connection_string()
    await asyncio.to_thread(_upload_blob_bytes, conn, container, blob_path, data)


async def download_blob_bytes(container: str, blob_path: str) -> bytes:
    """Download binary content from Azure Blob Storage."""
    conn = _get_connection_string()
    return await asyncio.to_thread(_download_blob_bytes, conn, container, blob_path)


async def generate_blob_sas_url(container: str, blob_path: str, expiry_hours: int = 24) -> str:
    """Generate a time-limited SAS download URL for a blob.

    Requires a connection string with AccountKey= (not compatible with Managed Identity).
    """
    conn = _get_connection_string()
    return await asyncio.to_thread(_generate_blob_sas_url, conn, container, blob_path, expiry_hours)
