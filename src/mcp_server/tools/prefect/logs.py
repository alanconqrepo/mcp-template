from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.prefect_client import get_prefect_client, raise_for_status

_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


@mcp.tool(
    description=(
        "Retrieve logs for a Prefect flow run. Supports filtering by minimum log level "
        "(DEBUG, INFO, WARNING, ERROR, CRITICAL) and pagination. "
        "Returns timestamp, level name, logger name, message and task_run_id for each log entry."
    )
)
async def prefect_get_flow_run_logs(
    flow_run_id: Annotated[str, Field(description="UUID of the flow run.")],
    min_level: Annotated[
        str,
        Field(description="Minimum log level to include: DEBUG, INFO, WARNING, ERROR, CRITICAL."),
    ] = "INFO",
    limit: Annotated[int, Field(description="Maximum number of log entries to return.", ge=1, le=1000)] = 100,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    async with trace_tool("prefect_get_flow_run_logs", inputs={"flow_run_id": flow_run_id, "min_level": min_level, "limit": limit}):
        level_int = _LOG_LEVELS.get(min_level.upper())
        if level_int is None:
            return {"error": f"Invalid min_level '{min_level}'. Valid values: {list(_LOG_LEVELS)}"}

        body = {
            "logs": {
                "flow_run_id": {"any_": [flow_run_id]},
                "level": {"ge_": level_int},
            },
            "limit": limit,
            "offset": offset,
        }

        async with get_prefect_client() as client:
            response = await client.post("logs/filter", json=body)
            await raise_for_status(response)
            entries = response.json()

        level_names = {v: k for k, v in _LOG_LEVELS.items()}

        result = [
            {
                "timestamp": e.get("timestamp"),
                "level": level_names.get(e.get("level"), str(e.get("level"))),
                "logger": e.get("name"),
                "message": e.get("message"),
                "task_run_id": e.get("task_run_id"),
            }
            for e in entries
        ]
        return {"logs": result, "total": len(result), "flow_run_id": flow_run_id}


@mcp.tool(
    description=(
        "Retrieve logs for a specific Prefect task run within a flow. "
        "Useful for inspecting the output of a single step in a flow run. "
        "Returns timestamp, level name, logger name and message for each log entry."
    )
)
async def prefect_get_task_run_logs(
    task_run_id: Annotated[str, Field(description="UUID of the task run.")],
    min_level: Annotated[
        str,
        Field(description="Minimum log level to include: DEBUG, INFO, WARNING, ERROR, CRITICAL."),
    ] = "INFO",
    limit: Annotated[int, Field(description="Maximum number of log entries to return.", ge=1, le=1000)] = 100,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    async with trace_tool("prefect_get_task_run_logs", inputs={"task_run_id": task_run_id, "min_level": min_level, "limit": limit}):
        level_int = _LOG_LEVELS.get(min_level.upper())
        if level_int is None:
            return {"error": f"Invalid min_level '{min_level}'. Valid values: {list(_LOG_LEVELS)}"}

        body = {
            "logs": {
                "task_run_id": {"any_": [task_run_id]},
                "level": {"ge_": level_int},
            },
            "limit": limit,
            "offset": offset,
        }

        async with get_prefect_client() as client:
            response = await client.post("logs/filter", json=body)
            await raise_for_status(response)
            entries = response.json()

        level_names = {v: k for k, v in _LOG_LEVELS.items()}

        result = [
            {
                "timestamp": e.get("timestamp"),
                "level": level_names.get(e.get("level"), str(e.get("level"))),
                "logger": e.get("name"),
                "message": e.get("message"),
            }
            for e in entries
        ]
        return {"logs": result, "total": len(result), "task_run_id": task_run_id}
