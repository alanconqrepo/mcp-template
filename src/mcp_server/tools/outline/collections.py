from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.outline_client import get_outline_client, outline_post


def _slim_collection(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "description": c.get("description"),
        "color": c.get("color"),
        "icon": c.get("icon"),
        "url": c.get("url"),
    }


def _count_tree_nodes(nodes: list) -> int:
    count = 0
    for node in nodes:
        count += 1
        count += _count_tree_nodes(node.get("children", []))
    return count


@mcp.tool(description=(
    "List all collections in Outline. "
    "Returns id, name, description, color, icon and url for each collection."
))
async def outline_list_collections(
    limit: Annotated[int, Field(description="Number of collections to return (max 25)", ge=1, le=25)] = 25,
    offset: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
) -> dict:
    async with trace_tool("outline_list_collections", inputs={"limit": limit}):
        async with get_outline_client() as client:
            data = await outline_post(client, "collections.list", {"limit": limit, "offset": offset})
        cols = data.get("data", [])
        return {
            "collections": [_slim_collection(c) for c in cols],
            "total": len(cols),
            "offset": offset,
            "next_offset": offset + len(cols) if len(cols) == limit else None,
        }


@mcp.tool(description="Retrieve details of a specific Outline collection by its UUID.")
async def outline_get_collection(
    collection_id: Annotated[str, Field(description="UUID of the collection")],
) -> dict:
    async with trace_tool("outline_get_collection", inputs={"collection_id": collection_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "collections.info", {"id": collection_id})
        return _slim_collection(data.get("data", {}))


@mcp.tool(description="Create a new collection in Outline.")
async def outline_create_collection(
    name: Annotated[str, Field(description="Collection name")],
    description: Annotated[str | None, Field(description="Optional description")] = None,
    color: Annotated[str | None, Field(description="Hex color code, e.g. '#FF5733'")] = None,
    icon: Annotated[str | None, Field(description="Emoji or icon name for the collection")] = None,
    permission: Annotated[str | None, Field(description="Default permission: 'read' | 'read_write' | null (private)")] = None,
) -> dict:
    async with trace_tool("outline_create_collection", inputs={"name": name}):
        async with get_outline_client() as client:
            data = await outline_post(client, "collections.create", {
                "name": name,
                "description": description,
                "color": color,
                "icon": icon,
                "permission": permission,
            })
        c = data.get("data", {})
        return {"id": c.get("id"), "name": c.get("name"), "url": c.get("url")}


@mcp.tool(description="Update an existing Outline collection. Only the fields you provide are changed.")
async def outline_update_collection(
    collection_id: Annotated[str, Field(description="UUID of the collection to update")],
    name: Annotated[str | None, Field(description="New name")] = None,
    description: Annotated[str | None, Field(description="New description")] = None,
    color: Annotated[str | None, Field(description="New hex color code")] = None,
    icon: Annotated[str | None, Field(description="New emoji or icon name")] = None,
    permission: Annotated[str | None, Field(description="New default permission: 'read' | 'read_write' | null")] = None,
) -> dict:
    async with trace_tool("outline_update_collection", inputs={"collection_id": collection_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "collections.update", {
                "id": collection_id,
                "name": name,
                "description": description,
                "color": color,
                "icon": icon,
                "permission": permission,
            })
        c = data.get("data", {})
        return {"id": c.get("id"), "name": c.get("name"), "url": c.get("url")}


@mcp.tool(description=(
    "Delete an Outline collection and all documents within it. "
    "This is a destructive operation — all documents in the collection are permanently deleted."
))
async def outline_delete_collection(
    collection_id: Annotated[str, Field(description="UUID of the collection to delete")],
) -> dict:
    async with trace_tool("outline_delete_collection", inputs={"collection_id": collection_id}):
        async with get_outline_client() as client:
            await outline_post(client, "collections.delete", {"id": collection_id})
        return {"deleted": True, "collection_id": collection_id}


@mcp.tool(description=(
    "List all documents in an Outline collection as a nested tree. "
    "Useful for understanding the full structure of a collection without pagination. "
    "Returns title, id, url and nesting depth for each document."
))
async def outline_list_collection_documents(
    collection_id: Annotated[str, Field(description="UUID of the collection")],
) -> dict:
    async with trace_tool("outline_list_collection_documents", inputs={"collection_id": collection_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "collections.documents", {"id": collection_id})
        tree = data.get("data", [])
        return {
            "collection_id": collection_id,
            "tree": tree,
            "total": _count_tree_nodes(tree),
        }
