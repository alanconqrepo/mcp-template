from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.sql_connection import fetch_rows, get_connection

_CONN = Field(description="Named SQL connection to use (uses default if omitted)")
_DB = Field(description="Database name (uses connection default if omitted)")


@mcp.tool(description="Get the MS_Description comment for a table and all its columns.")
async def sql_get_descriptions(
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, Field(description="Schema name (e.g. 'dbo')")],
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_get_descriptions", inputs={"schema": schema, "table": table}):
        def _run() -> dict:
            fqn = f"{schema}.{table}"
            with get_connection(connection, database) as conn:
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT CAST(ep.value AS NVARCHAR(MAX))
                    FROM sys.extended_properties ep
                    WHERE ep.major_id = OBJECT_ID(?) AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                    """,
                    (fqn,),
                )
                row = cur.fetchone()
                table_description = row[0] if row else None

                cur.execute(
                    """
                    SELECT
                        c.name AS column_name,
                        c.column_id,
                        CAST(ep.value AS NVARCHAR(MAX)) AS description
                    FROM sys.columns c
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = c.object_id AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
                    WHERE c.object_id = OBJECT_ID(?)
                    ORDER BY c.column_id
                    """,
                    (fqn,),
                )
                columns = fetch_rows(cur)

                return {"table_description": table_description, "columns": columns}

        result = await asyncio.to_thread(_run)
        return {"schema": schema, "table": table, **result}


@mcp.tool(description="Create or update the MS_Description comment on a table or one of its columns.")
async def sql_update_description(
    description: Annotated[str, Field(description="New description text to set")],
    table: Annotated[str, Field(description="Table name")],
    schema: Annotated[str, Field(description="Schema name (e.g. 'dbo')")],
    column: Annotated[str | None, Field(description="Column name — omit to update the table-level description")] = None,
    database: Annotated[str | None, _DB] = None,
    connection: Annotated[str | None, _CONN] = None,
) -> dict:
    async with trace_tool("sql_update_description", inputs={"schema": schema, "table": table, "column": column}):
        def _run() -> bool:
            fqn = f"{schema}.{table}"
            with get_connection(connection, database) as conn:
                cur = conn.cursor()
                if column:
                    cur.execute(
                        """
                        SELECT 1 FROM sys.extended_properties
                        WHERE major_id = OBJECT_ID(?)
                          AND minor_id = COLUMNPROPERTY(OBJECT_ID(?), ?, 'ColumnId')
                          AND name = 'MS_Description'
                        """,
                        (fqn, fqn, column),
                    )
                    exists = cur.fetchone() is not None
                    proc = "sp_updateextendedproperty" if exists else "sp_addextendedproperty"
                    cur.execute(
                        f"EXEC {proc} N'MS_Description', ?, N'SCHEMA', ?, N'TABLE', ?, N'COLUMN', ?",  # noqa: S608
                        (description, schema, table, column),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 1 FROM sys.extended_properties
                        WHERE major_id = OBJECT_ID(?) AND minor_id = 0 AND name = 'MS_Description'
                        """,
                        (fqn,),
                    )
                    exists = cur.fetchone() is not None
                    proc = "sp_updateextendedproperty" if exists else "sp_addextendedproperty"
                    cur.execute(
                        f"EXEC {proc} N'MS_Description', ?, N'SCHEMA', ?, N'TABLE', ?",  # noqa: S608
                        (description, schema, table),
                    )
                return exists

        existed = await asyncio.to_thread(_run)
        target = f"{schema}.{table}" + (f".{column}" if column else "")
        return {
            "action": "updated" if existed else "created",
            "target": target,
            "description": description,
        }
