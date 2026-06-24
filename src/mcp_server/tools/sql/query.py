from __future__ import annotations

import asyncio
import re
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.sql_connection import get_connection

_CONN = Field(description="Named SQL connection to use (uses default if omitted)")
_DB = Field(description="Database name (uses connection default if omitted)")
_MAX_ROWS = Field(description="Maximum number of rows to return", ge=1, le=5000)

_SAFE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_select(query: str) -> bool:
    """Accept SELECT and CTEs (WITH ... SELECT); reject everything else."""
    stripped = query.strip().upper()
    return stripped.startswith("SELECT") or stripped.startswith("WITH")


def _rows_to_dict(cursor) -> tuple[list[str], list[dict]]:
    cols = [d[0] for d in cursor.description] if cursor.description else []
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    return cols, rows


@mcp.tool(description="Execute a SQL SELECT query and return results as a list of rows. Only SELECT statements and CTEs are allowed.")
async def sql_execute_query(
    query: Annotated[str, Field(description="SQL SELECT statement to execute")],
    max_rows: Annotated[int, _MAX_ROWS] = 100,
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_execute_query", inputs={"query_length": len(query), "max_rows": max_rows}):
        if not _is_select(query):
            return {"error": "Only SELECT queries and CTEs are allowed"}

        def _run() -> dict:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(query)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]
                return {"columns": cols, "rows": rows, "row_count": len(rows)}

        return await asyncio.to_thread(_run)


@mcp.tool(description="Read the content of a global temporary table (##table_name). Only global temp tables (##) are accessible across sessions.")
async def sql_read_temp_table(
    table_name: Annotated[str, Field(description="Global temp table name, with or without ## prefix (e.g. 'results' or '##results')")],
    max_rows: Annotated[int, _MAX_ROWS] = 100,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_read_temp_table", inputs={"table_name": table_name}):
        clean = table_name.lstrip("#")
        if not _SAFE_NAME_RE.match(clean):
            return {"error": "Invalid table name: only letters, digits, and underscores allowed"}
        name = f"##{clean}"

        def _run() -> dict:
            with get_connection(connection) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM {name}")  # noqa: S608
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]
                return {"table": name, "columns": cols, "rows": rows, "row_count": len(rows)}

        return await asyncio.to_thread(_run)


@mcp.tool(description="Get a sample of rows from a table without writing SQL.")
async def sql_get_sample_data(
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, Field(description="Schema name (e.g. 'dbo')")],
    max_rows: Annotated[int, _MAX_ROWS] = 20,
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_sample_data", inputs={"schema": schema, "table": table}):
        def _run() -> dict:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM [{schema}].[{table}]")  # noqa: S608
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]
                return {"schema": schema, "table": table, "columns": cols, "rows": rows, "row_count": len(rows)}

        return await asyncio.to_thread(_run)
