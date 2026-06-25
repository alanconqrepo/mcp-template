from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.outline_client import get_outline_client, outline_post


@mcp.tool(description=(
    "Full-text search across Outline documents. "
    "Optionally scope the search to a specific collection or filter by date range. "
    "Returns document metadata with matching context snippets and a relevance ranking."
))
async def outline_search_documents(
    query: Annotated[str, Field(description="Search keywords or phrase")],
    collection_id: Annotated[str | None, Field(description="Limit search to this collection UUID")] = None,
    limit: Annotated[int, Field(description="Maximum number of results (max 25)", ge=1, le=25)] = 10,
    offset: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
    date_filter: Annotated[str | None, Field(description="Filter by recency: 'day' | 'week' | 'month' | 'year'")] = None,
) -> dict:
    async with trace_tool("outline_search_documents", inputs={"query": query, "collection_id": collection_id}):
        async with get_outline_client() as client:
            data = await outline_post(client, "documents.search", {
                "query": query,
                "collectionId": collection_id,
                "limit": limit,
                "offset": offset,
                "dateFilter": date_filter,
            })
        results = data.get("data", [])
        return {
            "results": [
                {
                    "document": {
                        "id": r.get("document", {}).get("id"),
                        "title": r.get("document", {}).get("title"),
                        "url": r.get("document", {}).get("url"),
                        "collectionId": r.get("document", {}).get("collectionId"),
                        "updatedAt": r.get("document", {}).get("updatedAt"),
                    },
                    "context": r.get("context"),
                    "ranking": r.get("ranking"),
                }
                for r in results
            ],
            "total": len(results),
            "offset": offset,
            "next_offset": offset + len(results) if len(results) == limit else None,
        }
