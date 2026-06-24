from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.prefect_client import get_prefect_client, raise_for_status

_VALID_STATES = {"SCHEDULED", "PENDING", "RUNNING", "COMPLETED", "FAILED", "CRASHED", "CANCELLING", "CANCELLED", "PAUSED"}


@mcp.tool(
    description=(
        "List Prefect flow runs with optional filters on state and deployment name. "
        "Returns id, name, state, start/end times and duration for each run. "
        "Valid states: SCHEDULED, PENDING, RUNNING, COMPLETED, FAILED, CRASHED, CANCELLING, CANCELLED, PAUSED."
    )
)
async def prefect_list_flow_runs(
    status: Annotated[
        str | None,
        Field(description="Filter by state type: RUNNING, COMPLETED, FAILED, CRASHED, CANCELLED, etc."),
    ] = None,
    deployment_name: Annotated[
        str | None,
        Field(description="Filter by deployment name (partial match, case-insensitive)."),
    ] = None,
    limit: Annotated[int, Field(description="Maximum number of runs to return.", ge=1, le=200)] = 20,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    async with trace_tool("prefect_list_flow_runs", inputs={"status": status, "deployment_name": deployment_name, "limit": limit}):
        if status and status.upper() not in _VALID_STATES:
            return {"error": f"Invalid status '{status}'. Valid values: {sorted(_VALID_STATES)}"}

        body: dict = {"limit": limit, "offset": offset, "sort": "START_TIME_DESC"}

        flow_run_filter: dict = {}
        if status:
            flow_run_filter["state"] = {"type": {"any_": [status.upper()]}}
        if flow_run_filter:
            body["flow_runs"] = flow_run_filter

        if deployment_name:
            body["deployments"] = {"name": {"like_": f"%{deployment_name}%"}}

        async with get_prefect_client() as client:
            response = await client.post("flow_runs/filter", json=body)
            await raise_for_status(response)
            runs = response.json()

        result = [
            {
                "id": r["id"],
                "name": r.get("name"),
                "state_type": r.get("state_type"),
                "state_name": r.get("state_name"),
                "deployment_id": r.get("deployment_id"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "total_run_time": r.get("total_run_time"),
                "tags": r.get("tags", []),
            }
            for r in runs
        ]
        return {"flow_runs": result, "total": len(result)}


@mcp.tool(
    description=(
        "Get the full details of a specific Prefect flow run by its ID. "
        "Returns state, parameters used, work pool, run duration and all metadata."
    )
)
async def prefect_get_flow_run(
    flow_run_id: Annotated[str, Field(description="UUID of the flow run.")],
) -> dict:
    async with trace_tool("prefect_get_flow_run", inputs={"flow_run_id": flow_run_id}):
        async with get_prefect_client() as client:
            response = await client.get(f"flow_runs/{flow_run_id}")
            await raise_for_status(response)
            r = response.json()

        return {
            "id": r["id"],
            "name": r.get("name"),
            "state_type": r.get("state_type"),
            "state_name": r.get("state_name"),
            "state_message": (r.get("state") or {}).get("message"),
            "deployment_id": r.get("deployment_id"),
            "flow_id": r.get("flow_id"),
            "parameters": r.get("parameters", {}),
            "tags": r.get("tags", []),
            "start_time": r.get("start_time"),
            "end_time": r.get("end_time"),
            "expected_start_time": r.get("expected_start_time"),
            "total_run_time": r.get("total_run_time"),
            "run_count": r.get("run_count"),
            "work_pool_name": r.get("work_pool_name"),
            "work_queue_name": r.get("work_queue_name"),
        }
