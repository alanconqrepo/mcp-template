from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.azure_blob import get_blob_text


@mcp.tool(description="Read the pre-computed metadata documentation (.md file) for a table or view from Azure Blob Storage.")
async def sql_get_blob_metadata(
    object_name: Annotated[str, Field(description="Table or view name")],
    schema: Annotated[str, Field(description="Schema name (e.g. 'dbo')")],
    object_type: Annotated[str, Field(description="Object type for display purposes (e.g. 'table', 'view')")] = "table",
) -> dict:
    async with trace_tool("sql_get_blob_metadata", inputs={"schema": schema, "object_name": object_name}):
        try:
            content = await get_blob_text(schema, object_name)
            return {
                "schema": schema,
                "object_name": object_name,
                "object_type": object_type,
                "metadata": content,
            }
        except Exception as exc:
            return {"error": str(exc), "schema": schema, "object_name": object_name}
