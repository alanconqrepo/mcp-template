from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.outline_client import get_outline_client, outline_post


def _slim_doc(d: dict) -> dict:
    return {
        "id": d.get("id"),
        "title": d.get("title"),
        "collectionId": d.get("collectionId"),
        "parentDocumentId": d.get("parentDocumentId"),
        "createdAt": d.get("createdAt"),
        "updatedAt": d.get("updatedAt"),
        "publishedAt": d.get("publishedAt"),
        "archivedAt": d.get("archivedAt"),
        "url": d.get("url"),
    }


@mcp.tool(description=(
    "List documents in Outline. Optionally filter by collection or user. "
    "Supports sort order and pagination. Returns id, title, collection, dates and url. "
    "Use next_offset to fetch the next page."
))
async def outline_list_documents(
    collection_id: Annotated[str | None, Field(description="Filter to a specific collection UUID")] = None,
    user_id: Annotated[str | None, Field(description="Filter to documents created by this user UUID")] = None,
    sort: Annotated[str, Field(description="Sort field: title | createdAt | updatedAt | publishedAt | index")] = "updatedAt",
    direction: Annotated[str, Field(description="Sort direction: ASC or DESC")] = "DESC",
    limit: Annotated[int, Field(description="Number of documents to return (max 25)", ge=1, le=25)] = 25,
    offset: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
) -> dict:
    async with trace_tool("outline_list_documents", inputs={"collection_id": collection_id, "limit": limit}):
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.list", {
                "collectionId": collection_id,
                "userId": user_id,
                "sort": sort,
                "direction": direction,
                "limit": limit,
                "offset": offset,
            })
        docs = data.get("data", [])
        return {
            "documents": [_slim_doc(d) for d in docs],
            "total": len(docs),
            "offset": offset,
            "limit": limit,
            "next_offset": offset + len(docs) if len(docs) == limit else None,
        }


@mcp.tool(description=(
    "Retrieve the full content of an Outline document by its UUID. "
    "Returns title, Markdown text, collection, metadata and author info."
))
async def outline_get_document(
    document_id: Annotated[str, Field(description="UUID of the document")],
) -> dict:
    async with trace_tool("outline_get_document", inputs={"document_id": document_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.info", {"id": document_id})
        d = data.get("data", {})
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "text": d.get("text"),
            "collectionId": d.get("collectionId"),
            "parentDocumentId": d.get("parentDocumentId"),
            "createdAt": d.get("createdAt"),
            "updatedAt": d.get("updatedAt"),
            "publishedAt": d.get("publishedAt"),
            "archivedAt": d.get("archivedAt"),
            "url": d.get("url"),
            "createdBy": (d.get("createdBy") or {}).get("name"),
            "updatedBy": (d.get("updatedBy") or {}).get("name"),
        }


@mcp.tool(description=(
    "Create a new document in Outline. "
    "Place it in a collection and optionally nest it under a parent document. "
    "Content is Markdown. Set publish=True to make it immediately visible."
))
async def outline_create_document(
    title: Annotated[str, Field(description="Document title")],
    collection_id: Annotated[str, Field(description="UUID of the collection to place the document in")],
    text: Annotated[str, Field(description="Document content in Markdown")] = "",
    parent_document_id: Annotated[str | None, Field(description="UUID of the parent document for nesting")] = None,
    publish: Annotated[bool, Field(description="Publish immediately (True) or save as draft (False)")] = True,
) -> dict:
    async with trace_tool("outline_create_document", inputs={"title": title, "collection_id": collection_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.create", {
                "title": title,
                "collectionId": collection_id,
                "text": text,
                "parentDocumentId": parent_document_id,
                "publish": publish,
            })
        d = data.get("data", {})
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "url": d.get("url"),
            "collectionId": d.get("collectionId"),
            "publishedAt": d.get("publishedAt"),
        }


@mcp.tool(description=(
    "Update an existing Outline document. Only the fields you provide are changed. "
    "Set append=True to add text at the end of the document instead of replacing the content."
))
async def outline_update_document(
    document_id: Annotated[str, Field(description="UUID of the document to update")],
    title: Annotated[str | None, Field(description="New title")] = None,
    text: Annotated[str | None, Field(description="New Markdown content (or text to append)")] = None,
    publish: Annotated[bool | None, Field(description="Change publish state")] = None,
    append: Annotated[bool, Field(description="If True, text is appended to existing content instead of replacing it")] = False,
) -> dict:
    async with trace_tool("outline_update_document", inputs={"document_id": document_id}):
        body: dict = {"id": document_id, "append": append}
        if title is not None:
            body["title"] = title
        if text is not None:
            body["text"] = text
        if publish is not None:
            body["publish"] = publish
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.update", body)
        d = data.get("data", {})
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "updatedAt": d.get("updatedAt"),
            "url": d.get("url"),
        }


@mcp.tool(description=(
    "Delete an Outline document. "
    "By default moves it to trash (recoverable). Set permanent=True to permanently destroy it with no recovery."
))
async def outline_delete_document(
    document_id: Annotated[str, Field(description="UUID of the document to delete")],
    permanent: Annotated[bool, Field(description="If True, permanently deletes with no recovery possible")] = False,
) -> dict:
    async with trace_tool("outline_delete_document", inputs={"document_id": document_id, "permanent": permanent}):
        async with get_outline_client() as client:
            await outline_post(client, "documents.delete", {"id": document_id, "permanent": permanent})
        return {"deleted": True, "document_id": document_id, "permanent": permanent}


@mcp.tool(description=(
    "Archive an Outline document. "
    "Archived documents are hidden from the main view but not deleted and can be restored later."
))
async def outline_archive_document(
    document_id: Annotated[str, Field(description="UUID of the document to archive")],
) -> dict:
    async with trace_tool("outline_archive_document", inputs={"document_id": document_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.archive", {"id": document_id})
        d = data.get("data", {})
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "archivedAt": d.get("archivedAt"),
        }


@mcp.tool(description=(
    "Move an Outline document to a different collection and/or parent document. "
    "Useful for reorganizing the knowledge base hierarchy."
))
async def outline_move_document(
    document_id: Annotated[str, Field(description="UUID of the document to move")],
    collection_id: Annotated[str, Field(description="UUID of the target collection")],
    parent_document_id: Annotated[str | None, Field(description="UUID of the new parent document, or omit to place at collection root")] = None,
) -> dict:
    async with trace_tool("outline_move_document", inputs={"document_id": document_id, "collection_id": collection_id}):
        async with get_outline_client() as client:
            await outline_post(client, "documents.move", {
                "id": document_id,
                "collectionId": collection_id,
                "parentDocumentId": parent_document_id,
            })
        return {"document_id": document_id, "collection_id": collection_id}
