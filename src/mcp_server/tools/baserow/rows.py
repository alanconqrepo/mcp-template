from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.baserow_client import get_baserow_client, raise_for_status

_TABLE = Field(description="Baserow table ID")
_ROW = Field(description="Row ID")


@mcp.tool(description="List rows in a Baserow table. Supports pagination, full-text search, and ordering.")
async def baserow_list_rows(
    table_id: Annotated[int, _TABLE],
    page: Annotated[int, Field(description="Page number (1-based)", ge=1)] = 1,
    size: Annotated[int, Field(description="Number of rows per page (max 200)", ge=1, le=200)] = 100,
    search: Annotated[str | None, Field(description="Optional search term applied across all text fields")] = None,
    order_by: Annotated[str | None, Field(description="Field name to sort by; prefix with '-' for descending (e.g. '-Name')")] = None,
) -> dict:
    async with trace_tool("baserow_list_rows", inputs={"table_id": table_id, "page": page, "size": size}):
        params: dict = {"user_field_names": "true", "page": page, "size": size}
        if search:
            params["search"] = search
        if order_by:
            params["order_by"] = order_by
        async with get_baserow_client() as client:
            response = await client.get(f"/api/database/rows/table/{table_id}/", params=params)
            await raise_for_status(response)
            return response.json()


@mcp.tool(description="Get a single row from a Baserow table by its row ID.")
async def baserow_get_row(
    table_id: Annotated[int, _TABLE],
    row_id: Annotated[int, _ROW],
) -> dict:
    async with trace_tool("baserow_get_row", inputs={"table_id": table_id, "row_id": row_id}):
        async with get_baserow_client() as client:
            response = await client.get(
                f"/api/database/rows/table/{table_id}/{row_id}/",
                params={"user_field_names": "true"},
            )
            await raise_for_status(response)
            return response.json()


@mcp.tool(description="Create a new row in a Baserow table.")
async def baserow_create_row(
    table_id: Annotated[int, _TABLE],
    fields: Annotated[dict, Field(description="Mapping of field names to values for the new row")],
) -> dict:
    async with trace_tool("baserow_create_row", inputs={"table_id": table_id}):
        async with get_baserow_client() as client:
            response = await client.post(
                f"/api/database/rows/table/{table_id}/",
                params={"user_field_names": "true"},
                json=fields,
            )
            await raise_for_status(response)
            return response.json()


@mcp.tool(description="Update fields on an existing Baserow row (PATCH — only listed fields are changed).")
async def baserow_update_row(
    table_id: Annotated[int, _TABLE],
    row_id: Annotated[int, _ROW],
    fields: Annotated[dict, Field(description="Mapping of field names to new values")],
) -> dict:
    async with trace_tool("baserow_update_row", inputs={"table_id": table_id, "row_id": row_id}):
        async with get_baserow_client() as client:
            response = await client.patch(
                f"/api/database/rows/table/{table_id}/{row_id}/",
                params={"user_field_names": "true"},
                json=fields,
            )
            await raise_for_status(response)
            return response.json()


@mcp.tool(description="Delete a row from a Baserow table. This action is permanent.")
async def baserow_delete_row(
    table_id: Annotated[int, _TABLE],
    row_id: Annotated[int, _ROW],
) -> dict:
    async with trace_tool("baserow_delete_row", inputs={"table_id": table_id, "row_id": row_id}):
        async with get_baserow_client() as client:
            response = await client.delete(f"/api/database/rows/table/{table_id}/{row_id}/")
            await raise_for_status(response)
        return {"deleted": True, "table_id": table_id, "row_id": row_id}
