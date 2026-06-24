from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp

_CONTAINER = Field(description="Container name (uses AZURE_BLOB_CONTAINER_NAME from config if omitted)")


def _download(connection_string: str, container: str, blob_path: str, encoding: str) -> str:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = client.get_blob_client(container=container, blob=blob_path)
    return blob_client.download_blob().readall().decode(encoding)


@mcp.tool(description="Download and return the text content of a blob (txt, json, csv, md, xml…).")
async def blob_get_content(
    blob_path: Annotated[str, Field(description="Path of the blob within the container (e.g. 'folder/file.json')")],
    container: Annotated[str | None, _CONTAINER] = None,
    encoding: Annotated[str, Field(description="Text encoding of the file")] = "utf-8",
) -> dict:
    async with trace_tool("blob_get_content", inputs={"container": container, "blob_path": blob_path}):
        from mcp_server.config import get_settings

        settings = get_settings()
        if not settings.AZURE_BLOB_CONNECTION_STRING:
            return {"error": "AZURE_BLOB_CONNECTION_STRING is not configured"}
        resolved_container = container or settings.AZURE_BLOB_CONTAINER_NAME
        if not resolved_container:
            return {"error": "container is required (or set AZURE_BLOB_CONTAINER_NAME in config)"}

        try:
            content = await asyncio.to_thread(
                _download,
                settings.AZURE_BLOB_CONNECTION_STRING,
                resolved_container,
                blob_path,
                encoding,
            )
        except Exception as e:
            return {"error": str(e), "container": resolved_container, "blob_path": blob_path}

        return {"container": resolved_container, "blob_path": blob_path, "content": content}
