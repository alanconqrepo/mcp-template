from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp

_MAX_ROWS = Field(description="Maximum number of rows to return", ge=1, le=5000)
_CONTAINER = Field(description="Default container for azure:// URIs without an explicit container")


def _is_select(query: str) -> bool:
    stripped = query.strip().upper()
    return stripped.startswith("SELECT") or stripped.startswith("WITH")


def _run_query(connection_string: str, default_container: str, query: str, max_rows: int) -> dict:
    import duckdb

    conn = duckdb.connect()
    conn.execute("INSTALL azure; LOAD azure;")
    conn.execute(f"SET azure_storage_connection_string='{connection_string}';")
    if default_container:
        # lets DuckDB resolve bare paths like azure://path without repeating the container
        conn.execute(f"SET azure_account_name='{_extract_account(connection_string)}';")

    rel = conn.execute(query)
    cols = [d[0] for d in rel.description] if rel.description else []
    rows = [dict(zip(cols, row)) for row in rel.fetchmany(max_rows)]
    return {"columns": cols, "rows": rows, "row_count": len(rows)}


def _extract_account(connection_string: str) -> str:
    """Parse AccountName from a storage connection string."""
    for part in connection_string.split(";"):
        if part.startswith("AccountName="):
            return part.split("=", 1)[1]
    return ""


@mcp.tool(
    description=(
        "Execute a SQL SELECT query via DuckDB on Parquet files stored in Azure Blob Storage. "
        "Reference files using read_parquet('azure://{container}/{path}') or glob patterns "
        "like read_parquet('azure://mycontainer/data/*.parquet'). "
        "The Azure connection is configured server-side; no credentials needed in the query."
    )
)
async def blob_query_parquet(
    query: Annotated[str, Field(description="DuckDB SQL SELECT query referencing Parquet files via azure:// URIs")],
    max_rows: Annotated[int, _MAX_ROWS] = 100,
    container: Annotated[str | None, _CONTAINER] = None,
) -> dict:
    async with trace_tool("blob_query_parquet", inputs={"query_length": len(query), "max_rows": max_rows}):
        if not _is_select(query):
            return {"error": "Only SELECT queries and CTEs are allowed"}

        from mcp_server.config import get_settings

        settings = get_settings()
        if not settings.AZURE_BLOB_CONNECTION_STRING:
            return {"error": "AZURE_BLOB_CONNECTION_STRING is not configured"}

        resolved_container = container or settings.AZURE_BLOB_CONTAINER_NAME

        try:
            result = await asyncio.to_thread(
                _run_query,
                settings.AZURE_BLOB_CONNECTION_STRING,
                resolved_container,
                query,
                max_rows,
            )
        except Exception as e:
            return {"error": str(e)}

        return result
