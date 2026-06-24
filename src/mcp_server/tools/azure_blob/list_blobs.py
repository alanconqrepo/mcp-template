from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp

_CONTAINER = Field(description="Container name (uses AZURE_BLOB_CONTAINER_NAME from config if omitted)")
_PREFIX = Field(description="Filter blobs whose name starts with this prefix")


def _list(connection_string: str, container: str, prefix: str | None) -> list[dict]:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(connection_string)
    container_client = client.get_container_client(container)
    blobs = container_client.list_blobs(name_starts_with=prefix)
    return [
        {
            "name": b.name,
            "size_bytes": b.size,
            "last_modified": b.last_modified.isoformat() if b.last_modified else None,
            "content_type": b.content_settings.content_type if b.content_settings else None,
        }
        for b in blobs
    ]


@mcp.tool(description="List blobs in an Azure Blob Storage container, optionally filtered by prefix (starts_with).")
async def blob_list(
    prefix: Annotated[str | None, _PREFIX] = None,
    container: Annotated[str | None, _CONTAINER] = None,
) -> dict:
    async with trace_tool("blob_list", inputs={"container": container, "prefix": prefix}):
        from mcp_server.config import get_settings

        settings = get_settings()
        if not settings.AZURE_BLOB_CONNECTION_STRING:
            return {"error": "AZURE_BLOB_CONNECTION_STRING is not configured"}
        resolved_container = container or settings.AZURE_BLOB_CONTAINER_NAME
        if not resolved_container:
            return {"error": "container is required (or set AZURE_BLOB_CONTAINER_NAME in config)"}

        blobs = await asyncio.to_thread(
            _list, settings.AZURE_BLOB_CONNECTION_STRING, resolved_container, prefix
        )
        return {"container": resolved_container, "prefix": prefix, "blobs": blobs, "count": len(blobs)}
