from __future__ import annotations

import re
import uuid
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
        "Insert or update documents in a vector store collection. "
        "Each document must have a 'content' field (text to embed). "
        "Optional fields: 'id' (auto-generated UUID if absent), 'metadata' (arbitrary JSON dict). "
        "Existing documents with the same id are updated (upsert)."
    )
)
async def vector_store_upsert_documents(
    collection: Annotated[str, Field(description="Target collection name")],
    documents: Annotated[
        list[dict],
        Field(
            description=(
                "List of document objects. Each must have 'content' (str). "
                "Optional: 'id' (str), 'metadata' (dict)."
            )
        ),
    ],
) -> dict:
    async with trace_tool(
        "vector_store_upsert_documents",
        inputs={"collection": collection, "doc_count": len(documents)},
    ):
        err = _validate_collection(collection)
        if err:
            return {"error": err}

        if not documents:
            return {"collection": collection, "upserted": 0, "ids": []}

        for i, doc in enumerate(documents):
            if "content" not in doc or not isinstance(doc["content"], str):
                return {"error": f"Document at index {i} is missing a 'content' string field."}

        from mcp_server.utils.embedding_client import get_embeddings
        from mcp_server.utils.pgvector_pool import get_pool

        # Resolve IDs and prepare data
        ids = [doc.get("id") or str(uuid.uuid4()) for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata") or {} for doc in documents]

        embeddings = await get_embeddings(contents)

        pool = await get_pool()
        table = _table(collection)

        async with pool.connection() as conn:
            async with conn.transaction():
                import json
                for doc_id, content, embedding, metadata in zip(ids, contents, embeddings, metadatas):
                    await conn.execute(
                        f"""
                        INSERT INTO {table} (id, content, embedding, metadata, updated_at)
                        VALUES (%s, %s, %s, %s, now())
                        ON CONFLICT (id) DO UPDATE
                            SET content    = EXCLUDED.content,
                                embedding  = EXCLUDED.embedding,
                                metadata   = EXCLUDED.metadata,
                                updated_at = now()
                        """,
                        (doc_id, content, embedding, json.dumps(metadata)),
                    )
                # Sync document_count from actual row count
                await conn.execute(
                    "UPDATE vector_store_collections SET document_count = ("
                    f"    SELECT count(*) FROM {table}"
                    ") WHERE name = %s",
                    (collection,),
                )

        return {"collection": collection, "upserted": len(ids), "ids": ids}


@mcp.tool(
    description=(
        "Delete documents from a vector store collection. "
        "Provide either 'ids' (list of document IDs) or 'metadata_filter' (JSON dict, all key-value pairs must match), "
        "but not both."
    )
)
async def vector_store_delete_documents(
    collection: Annotated[str, Field(description="Collection name")],
    ids: Annotated[
        list[str] | None,
        Field(description="List of document IDs to delete"),
    ] = None,
    metadata_filter: Annotated[
        dict | None,
        Field(description="Delete documents whose metadata contains all specified key-value pairs"),
    ] = None,
) -> dict:
    async with trace_tool(
        "vector_store_delete_documents",
        inputs={"collection": collection},
    ):
        err = _validate_collection(collection)
        if err:
            return {"error": err}

        if ids is None and metadata_filter is None:
            return {"error": "Provide either 'ids' or 'metadata_filter'."}
        if ids is not None and metadata_filter is not None:
            return {"error": "Provide either 'ids' or 'metadata_filter', not both."}

        from mcp_server.utils.pgvector_pool import get_pool

        pool = await get_pool()
        table = _table(collection)

        async with pool.connection() as conn:
            async with conn.transaction():
                if ids is not None:
                    result = await conn.execute(
                        f"DELETE FROM {table} WHERE id = ANY(%s)", (ids,)
                    )
                else:
                    import json
                    result = await conn.execute(
                        f"DELETE FROM {table} WHERE metadata @> %s::jsonb",
                        (json.dumps(metadata_filter),),
                    )
                deleted = result.rowcount if result.rowcount is not None else 0
                await conn.execute(
                    "UPDATE vector_store_collections SET document_count = ("
                    f"    SELECT count(*) FROM {table}"
                    ") WHERE name = %s",
                    (collection,),
                )

        return {"collection": collection, "deleted": deleted}
