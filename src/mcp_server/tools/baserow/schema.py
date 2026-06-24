from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.baserow_client import get_baserow_client, raise_for_status


@mcp.tool(description="List all Baserow databases (applications) accessible with the configured token.")
async def baserow_list_databases() -> dict:
    async with trace_tool("baserow_list_databases"):
        async with get_baserow_client() as client:
            response = await client.get("/api/applications/")
            await raise_for_status(response)
            data = response.json()
        return {"databases": data, "count": len(data)}


@mcp.tool(description="List all tables in a Baserow database.")
async def baserow_list_tables(
    database_id: Annotated[int, Field(description="Baserow database (application) ID")],
) -> dict:
    async with trace_tool("baserow_list_tables", inputs={"database_id": database_id}):
        async with get_baserow_client() as client:
            response = await client.get(f"/api/database/tables/database/{database_id}/")
            await raise_for_status(response)
            data = response.json()
        return {"database_id": database_id, "tables": data, "count": len(data)}


@mcp.tool(description="List all fields (columns) of a Baserow table, including their names and types.")
async def baserow_list_fields(
    table_id: Annotated[int, Field(description="Baserow table ID")],
) -> dict:
    async with trace_tool("baserow_list_fields", inputs={"table_id": table_id}):
        async with get_baserow_client() as client:
            response = await client.get(f"/api/database/fields/table/{table_id}/")
            await raise_for_status(response)
            data = response.json()
        return {"table_id": table_id, "fields": data, "count": len(data)}
