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


@mcp.tool(description="Get the full definition of a table: columns, types, nullability, PK, FK, and indexes.")
async def sql_get_table_definition(
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_table_definition", inputs={"schema": schema, "table": table}):
        def _run() -> dict:
            fqn = f"{schema}.{table}"
            with get_connection(connection, database) as conn:
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT
                        c.name AS column_name,
                        t.name AS data_type,
                        CASE
                            WHEN t.name IN ('nvarchar', 'nchar') THEN c.max_length / 2
                            WHEN c.max_length = -1 THEN -1
                            ELSE c.max_length
                        END AS max_length,
                        c.precision,
                        c.scale,
                        c.is_nullable,
                        c.is_identity,
                        dc.definition AS default_value,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.columns c
                    JOIN sys.types t ON c.user_type_id = t.user_type_id
                    LEFT JOIN sys.default_constraints dc
                        ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = c.object_id AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
                    WHERE c.object_id = OBJECT_ID(?)
                    ORDER BY c.column_id
                    """,
                    (fqn,),
                )
                columns = fetch_rows(cur)

                cur.execute(
                    """
                    SELECT c.name
                    FROM sys.index_columns ic
                    JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                    WHERE ic.object_id = OBJECT_ID(?) AND i.is_primary_key = 1
                    ORDER BY ic.key_ordinal
                    """,
                    (fqn,),
                )
                primary_key = [row[0] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        fk.name AS fk_name,
                        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
                        SCHEMA_NAME(ro.schema_id) AS referenced_schema,
                        OBJECT_NAME(fkc.referenced_object_id) AS referenced_table,
                        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
                    FROM sys.foreign_keys fk
                    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                    JOIN sys.objects ro ON ro.object_id = fkc.referenced_object_id
                    WHERE fk.parent_object_id = OBJECT_ID(?)
                    """,
                    (fqn,),
                )
                foreign_keys = fetch_rows(cur)

                cur.execute(
                    """
                    SELECT
                        i.name AS index_name,
                        i.type_desc AS index_type,
                        i.is_unique,
                        STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                    WHERE i.object_id = OBJECT_ID(?) AND i.is_primary_key = 0 AND i.type > 0
                    GROUP BY i.name, i.type_desc, i.is_unique
                    ORDER BY i.name
                    """,
                    (fqn,),
                )
                indexes = fetch_rows(cur)

                return {
                    "columns": columns,
                    "primary_key": primary_key,
                    "foreign_keys": foreign_keys,
                    "indexes": indexes,
                }

        result = await asyncio.to_thread(_run)
        return {"schema": schema, "table": table, **result}


@mcp.tool(description="Get the SQL definition (CREATE VIEW body) of a view.")
async def sql_get_view_definition(
    view: Annotated[str, Field(description="View name")],
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_view_definition", inputs={"schema": schema, "view": view}):
        def _run() -> str | None:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", (f"{schema}.{view}",))
                row = cur.fetchone()
                return row[0] if row else None

        definition = await asyncio.to_thread(_run)
        if definition is None:
            return {"error": f"View '{schema}.{view}' not found"}
        return {"schema": schema, "view": view, "definition": definition}


@mcp.tool(description="Get the SQL body of a stored procedure.")
async def sql_get_procedure_definition(
    procedure: Annotated[str, Field(description="Stored procedure name")],
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_procedure_definition", inputs={"schema": schema, "procedure": procedure}):
        def _run() -> str | None:
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                cur.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", (f"{schema}.{procedure}",))
                row = cur.fetchone()
                return row[0] if row else None

        definition = await asyncio.to_thread(_run)
        if definition is None:
            return {"error": f"Procedure '{schema}.{procedure}' not found"}
        return {"schema": schema, "procedure": procedure, "definition": definition}


@mcp.tool(description="Get all foreign key relationships for a table — both outgoing (this table references others) and incoming (other tables reference this one).")
async def sql_get_relationships(
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, _SCHEMA],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_relationships", inputs={"schema": schema, "table": table}):
        def _run() -> dict:
            fqn = f"{schema}.{table}"
            with get_connection(connection, database) as conn:
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT
                        fk.name AS fk_name,
                        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
                        SCHEMA_NAME(ro.schema_id) AS referenced_schema,
                        OBJECT_NAME(fkc.referenced_object_id) AS referenced_table,
                        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
                    FROM sys.foreign_keys fk
                    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                    JOIN sys.objects ro ON ro.object_id = fkc.referenced_object_id
                    WHERE fk.parent_object_id = OBJECT_ID(?)
                    """,
                    (fqn,),
                )
                outgoing = fetch_rows(cur)

                cur.execute(
                    """
                    SELECT
                        fk.name AS fk_name,
                        SCHEMA_NAME(po.schema_id) AS parent_schema,
                        OBJECT_NAME(fkc.parent_object_id) AS parent_table,
                        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
                        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
                    FROM sys.foreign_keys fk
                    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                    JOIN sys.objects po ON po.object_id = fkc.parent_object_id
                    WHERE fk.referenced_object_id = OBJECT_ID(?)
                    """,
                    (fqn,),
                )
                incoming = fetch_rows(cur)

                return {"outgoing": outgoing, "incoming": incoming}

        result = await asyncio.to_thread(_run)
        return {"schema": schema, "table": table, **result}
