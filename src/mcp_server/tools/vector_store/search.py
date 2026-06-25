from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _validate_collection(name: str) -> str | None:
    if not _NAME_RE.match(name):
        return (
            "Invalid collection name. Use lowercase letters, digits, and underscores. "
            "Must start with a letter and be at most 63 characters."
        )
    return None


def _table(name: str) -> str:
    return f"vs_{name}"


@mcp.tool(
    description=(
        "Semantic similarity search in a vector store collection. "
        "The query is embedded and compared against stored document embeddings using cosine similarity. "
        "Returns documents ranked by relevance with their similarity scores (0.0–1.0). "
        "Optionally filter by metadata key-value pairs and/or minimum similarity threshold."
    )
)
async def vector_store_search(
    collection: Annotated[str, Field(description="Collection to search")],
    query: Annotated[str, Field(description="Natural language query to embed and search for")],
    top_k: Annotated[int, Field(description="Number of results to return", ge=1, le=100)] = 10,
    metadata_filter: Annotated[
        dict | None,
        Field(description="Only return documents whose metadata contains all specified key-value pairs"),
    ] = None,
    min_similarity: Annotated[
        float | None,
        Field(description="Minimum cosine similarity (0.0–1.0). Results below this threshold are excluded.", ge=0.0, le=1.0),
    ] = None,
) -> dict:
    async with trace_tool("vector_store_search", inputs={"collection": collection, "top_k": top_k}):
        err = _validate_collection(collection)
        if err:
            return {"error": err}

        from mcp_server.utils.embedding_client import get_embeddings
        from mcp_server.utils.pgvector_pool import get_pool

        query_embeddings = await get_embeddings([query])
        query_vector = query_embeddings[0]

        pool = await get_pool()
        table = _table(collection)

        async with pool.connection() as conn:
            if metadata_filter:
                import json
                rows = await (await conn.execute(
                    f"""
                    SELECT id, content, metadata, 1 - (embedding <=> %s::vector) AS similarity
                    FROM {table}
                    WHERE metadata @> %s::jsonb
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, json.dumps(metadata_filter), query_vector, top_k),
                )).fetchall()
            else:
                rows = await (await conn.execute(
                    f"""
                    SELECT id, content, metadata, 1 - (embedding <=> %s::vector) AS similarity
                    FROM {table}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, query_vector, top_k),
                )).fetchall()

        results = [
            {
                "id": r[0],
                "content": r[1],
                "metadata": r[2] if isinstance(r[2], dict) else {},
                "similarity": float(r[3]),
            }
            for r in rows
        ]

        if min_similarity is not None:
            results = [r for r in results if r["similarity"] >= min_similarity]

        return {"collection": collection, "query": query, "results": results, "count": len(results)}


@mcp.tool(
    description=(
        "Retrieve a single document by its ID from a vector store collection. "
        "Returns the document content and metadata without the embedding vector."
    )
)
async def vector_store_fetch_document(
    collection: Annotated[str, Field(description="Collection name")],
    id: Annotated[str, Field(description="Document ID to retrieve")],
) -> dict:
    async with trace_tool("vector_store_fetch_document", inputs={"collection": collection, "id": id}):
        err = _validate_collection(collection)
        if err:
            return {"error": err}

        from mcp_server.utils.pgvector_pool import get_pool

        pool = await get_pool()
        table = _table(collection)

        async with pool.connection() as conn:
            row = await (await conn.execute(
                f"SELECT id, content, metadata, created_at, updated_at FROM {table} WHERE id = %s",
                (id,),
            )).fetchone()

        if row is None:
            return {"error": "not_found", "id": id, "collection": collection}

        return {
            "id": row[0],
            "content": row[1],
            "metadata": row[2] if isinstance(row[2], dict) else {},
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None,
        }
