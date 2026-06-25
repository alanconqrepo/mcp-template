from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _validate_collection(name: str) -> str | None:
    """Return an error message if the name is invalid, else None."""
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
        "Create a new vector store collection (PostgreSQL table with HNSW index). "
        "The collection name must be lowercase letters, digits, or underscores. "
        "Idempotent: safe to call again if the collection already exists with the same dimensions."
    )
)
async def vector_store_create_collection(
    collection: Annotated[str, Field(description="Collection name (e.g. 'docs_fr', 'product_manuals')")],
    description: Annotated[str | None, Field(description="Optional human-readable description")] = None,
    dimensions: Annotated[
        int | None,
        Field(description="Embedding vector dimensions. Defaults to EMBEDDING_DIMENSIONS from config.", ge=1, le=4096),
    ] = None,
) -> dict:
    async with trace_tool("vector_store_create_collection", inputs={"collection": collection}):
        err = _validate_collection(collection)
        if err:
            return {"error": err}

        from mcp_server.config import get_settings
        from mcp_server.utils.pgvector_pool import get_pool

        dims = dimensions or get_settings().EMBEDDING_DIMENSIONS
        pool = await get_pool()

        async with pool.connection() as conn:
            # DDL requires autocommit — no implicit transaction wrapper
            await conn.set_autocommit(True)

            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS vector_store_collections (
                    name           TEXT PRIMARY KEY,
                    dimensions     INTEGER NOT NULL,
                    description    TEXT,
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                    document_count BIGINT NOT NULL DEFAULT 0
                )
            """)

            # Check for dimension conflict
            row = await (await conn.execute(
                "SELECT dimensions FROM vector_store_collections WHERE name = %s", (collection,)
            )).fetchone()
            if row is not None:
                existing_dims = row[0]
                if existing_dims != dims:
                    return {
                        "error": (
                            f"Collection '{collection}' already exists with {existing_dims} dimensions. "
                            f"Cannot change dimensions to {dims}."
                        )
                    }
                return {
                    "collection": collection,
                    "dimensions": existing_dims,
                    "created": False,
                    "message": "Collection already exists.",
                }

            table = _table(collection)
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id         TEXT PRIMARY KEY,
                    content    TEXT NOT NULL,
                    embedding  vector({dims}) NOT NULL,
                    metadata   JSONB NOT NULL DEFAULT '{{}}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {table}_hnsw_idx
                ON {table} USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {table}_metadata_idx
                ON {table} USING gin (metadata jsonb_path_ops)
            """)
            await conn.execute(
                "INSERT INTO vector_store_collections (name, dimensions, description) VALUES (%s, %s, %s)",
                (collection, dims, description),
            )

        return {"collection": collection, "dimensions": dims, "created": True}


@mcp.tool(description="List all vector store collections with their document counts and dimensions.")
async def vector_store_list_collections() -> dict:
    async with trace_tool("vector_store_list_collections", inputs={}):
        from mcp_server.utils.pgvector_pool import get_pool

        pool = await get_pool()
        async with pool.connection() as conn:
            # Ensure registry table exists (server may not have had create called yet)
            await conn.set_autocommit(True)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS vector_store_collections (
                    name           TEXT PRIMARY KEY,
                    dimensions     INTEGER NOT NULL,
                    description    TEXT,
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                    document_count BIGINT NOT NULL DEFAULT 0
                )
            """)
            rows = await (await conn.execute(
                "SELECT name, dimensions, description, created_at, document_count "
                "FROM vector_store_collections ORDER BY name"
            )).fetchall()

        collections = [
            {
                "name": r[0],
                "dimensions": r[1],
                "description": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "document_count": r[4],
            }
            for r in rows
        ]
        return {"collections": collections, "count": len(collections)}


@mcp.tool(
    description=(
        "Delete a vector store collection and all its documents. "
        "Requires confirm=true to prevent accidental data loss."
    )
)
async def vector_store_delete_collection(
    collection: Annotated[str, Field(description="Collection name to delete")],
    confirm: Annotated[bool, Field(description="Must be true to confirm deletion")] = False,
) -> dict:
    async with trace_tool("vector_store_delete_collection", inputs={"collection": collection}):
        if not confirm:
            return {"error": "Set confirm=true to delete the collection and all its documents."}

        err = _validate_collection(collection)
        if err:
            return {"error": err}

        from mcp_server.utils.pgvector_pool import get_pool

        pool = await get_pool()
        table = _table(collection)

        async with pool.connection() as conn:
            await conn.set_autocommit(True)
            # Count before drop
            count_row = await (await conn.execute(
                "SELECT document_count FROM vector_store_collections WHERE name = %s", (collection,)
            )).fetchone()
            if count_row is None:
                return {"error": f"Collection '{collection}' does not exist."}

            documents_removed = count_row[0]
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
            await conn.execute(
                "DELETE FROM vector_store_collections WHERE name = %s", (collection,)
            )

        return {"deleted": True, "collection": collection, "documents_removed": documents_removed}
