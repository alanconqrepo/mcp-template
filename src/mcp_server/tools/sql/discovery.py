from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.sql_connection import fetch_rows, get_connection

_CONN = Field(description="Named SQL connection to use (uses default if omitted)")
_DB = Field(description="Database name (uses connection default if omitted)")
_SCHEMA = Field(description="Schema name (e.g. 'dbo')")


@mcp.tool(description="List all databases available on the SQL Server.")
async def sql_list_databases(
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_list_databases"):
        def _run() -> list[str]:
            with get_connection(connection) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sys.databases WHERE state = 0 ORDER BY name")
                return [row[0] for row in cur.fetchall()]

        databases = await asyncio.to_thread(_run)
        return {"databases": databases, "count": len(databases)}


@mcp.tool(description="List all user schemas in a database.")
async def sql_list_schemas(
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_list_schemas"):
        _SYSTEM_SCHEMAS = frozenset({
            "sys", "guest", "INFORMATION_SCHEMA", "db_owner", "db_accessadmin",
            "db_securityadmin", "db_ddladmin", "db_backupoperator", "db_datareader",
            "db_datawriter", "db_denydatareader", "db_denydatawriter",
        })

        def _run() -> list[str]:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sys.schemas ORDER BY name")
                return [row[0] for row in cur.fetchall() if row[0] not in _SYSTEM_SCHEMAS]

        schemas = await asyncio.to_thread(_run)
        return {"schemas": schemas, "count": len(schemas)}


@mcp.tool(description="List all tables in a schema with approximate row counts and descriptions.")
async def sql_list_tables(
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_list_tables", inputs={"schema": schema}):
        def _run() -> list[dict]:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        t.name AS table_name,
                        ISNULL(SUM(p.rows), 0) AS approx_row_count,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.tables t
                    JOIN sys.schemas s ON s.schema_id = t.schema_id
                    LEFT JOIN sys.partitions p
                        ON p.object_id = t.object_id AND p.index_id IN (0, 1)
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                    WHERE s.name = ?
                    GROUP BY t.name, ep.value
                    ORDER BY t.name
                    """,
                    (schema,),
                )
                return fetch_rows(cur)

        tables = await asyncio.to_thread(_run)
        return {"schema": schema, "tables": tables, "count": len(tables)}


@mcp.tool(description="List all views in a schema with their descriptions.")
async def sql_list_views(
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_list_views", inputs={"schema": schema}):
        def _run() -> list[dict]:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        v.name AS view_name,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.views v
                    JOIN sys.schemas s ON s.schema_id = v.schema_id
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = v.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                    WHERE s.name = ?
                    ORDER BY v.name
                    """,
                    (schema,),
                )
                return fetch_rows(cur)

        views = await asyncio.to_thread(_run)
        return {"schema": schema, "views": views, "count": len(views)}


@mcp.tool(description="List all stored procedures in a schema with their descriptions.")
async def sql_list_procedures(
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_list_procedures", inputs={"schema": schema}):
        def _run() -> list[dict]:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        p.name AS procedure_name,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.procedures p
                    JOIN sys.schemas s ON s.schema_id = p.schema_id
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = p.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                    WHERE s.name = ?
                    ORDER BY p.name
                    """,
                    (schema,),
                )
                return fetch_rows(cur)

        procs = await asyncio.to_thread(_run)
        return {"schema": schema, "procedures": procs, "count": len(procs)}


@mcp.tool(description="Search for tables, views, procedures, and columns by keyword (partial name match).")
async def sql_search_objects(
    keyword: Annotated[str, Field(description="Keyword to search — matches any part of names, case-insensitive")],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_search_objects", inputs={"keyword": keyword}):
        def _run() -> list[dict]:
            like = f"%{keyword}%"
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        o.type_desc AS object_type,
                        SCHEMA_NAME(o.schema_id) AS schema_name,
                        o.name AS object_name,
                        NULL AS column_name,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.objects o
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = o.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                    WHERE o.name LIKE ? AND o.type IN ('U', 'V', 'P', 'FN', 'IF', 'TF')

                    UNION ALL

                    SELECT
                        'COLUMN' AS object_type,
                        SCHEMA_NAME(o.schema_id) AS schema_name,
                        o.name AS object_name,
                        c.name AS column_name,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.columns c
                    JOIN sys.objects o ON o.object_id = c.object_id
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = c.object_id AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
                    WHERE c.name LIKE ? AND o.type IN ('U', 'V')

                    ORDER BY object_type, schema_name, object_name
                    """,
                    (like, like),
                )
                return fetch_rows(cur)

        results = await asyncio.to_thread(_run)
        return {"keyword": keyword, "results": results, "count": len(results)}


@mcp.tool(description="Get row count, disk size (MB), and last statistics update date for a table.")
async def sql_get_table_stats(
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_table_stats", inputs={"schema": schema, "table": table}):
        def _run() -> dict | None:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        SUM(p.rows) AS row_count,
                        CAST(SUM(a.total_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS total_size_mb,
                        CAST(SUM(a.used_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS used_size_mb,
                        STATS_DATE(t.object_id, 1) AS last_stats_update
                    FROM sys.tables t
                    JOIN sys.schemas s ON s.schema_id = t.schema_id
                    JOIN sys.partitions p ON p.object_id = t.object_id
                    JOIN sys.allocation_units a ON a.container_id = p.partition_id
                    WHERE s.name = ? AND t.name = ?
                    GROUP BY t.object_id
                    """,
                    (schema, table),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return {
                    "row_count": row[0],
                    "total_size_mb": float(row[1]) if row[1] is not None else None,
                    "used_size_mb": float(row[2]) if row[2] is not None else None,
                    "last_stats_update": str(row[3]) if row[3] is not None else None,
                }

        stats = await asyncio.to_thread(_run)
        if stats is None:
            return {"error": f"Table '{schema}.{table}' not found"}
        return {"schema": schema, "table": table, **stats}
