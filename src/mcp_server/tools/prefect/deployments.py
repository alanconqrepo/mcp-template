from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.prefect_client import get_prefect_client, raise_for_status


@mcp.tool(
    description=(
        "List Prefect deployments available on this instance. "
        "Optionally filter by deployment name (partial match). "
        "Returns id, name, flow name, paused status, work pool and schedule summary."
    )
)
async def prefect_list_deployments(
    name_filter: Annotated[
        str | None,
        Field(description="Partial deployment name to filter on (case-insensitive)."),
    ] = None,
    limit: Annotated[int, Field(description="Maximum number of deployments to return.", ge=1, le=200)] = 20,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    async with trace_tool("prefect_list_deployments", inputs={"name_filter": name_filter, "limit": limit}):
        body: dict = {"limit": limit, "offset": offset}
        if name_filter:
            body["deployments"] = {"name": {"like_": f"%{name_filter}%"}}

        async with get_prefect_client() as client:
            response = await client.post("deployments/filter", json=body)
            await raise_for_status(response)
            deployments = response.json()

        result = [
            {
                "id": d["id"],
                "name": d.get("name"),
                "flow_id": d.get("flow_id"),
                "paused": d.get("paused"),
                "tags": d.get("tags", []),
                "work_pool_name": d.get("work_pool_name"),
                "schedules": [
                    {"active": s.get("active"), "schedule": s.get("schedule")}
                    for s in (d.get("schedules") or [])
                ],
                "description": d.get("description"),
            }
            for d in deployments
        ]
        return {"deployments": result, "total": len(result)}


@mcp.tool(
    description=(
        "Get full details of a Prefect deployment by its ID, including its parameter schema, "
        "schedules, work pool, tags and description."
    )
)
async def prefect_get_deployment(
    deployment_id: Annotated[str, Field(description="UUID of the deployment.")],
) -> dict:
    async with trace_tool("prefect_get_deployment", inputs={"deployment_id": deployment_id}):
        async with get_prefect_client() as client:
            response = await client.get(f"deployments/{deployment_id}")
            await raise_for_status(response)
            d = response.json()

        return {
            "id": d["id"],
            "name": d.get("name"),
            "flow_id": d.get("flow_id"),
            "paused": d.get("paused"),
            "tags": d.get("tags", []),
            "work_pool_name": d.get("work_pool_name"),
            "work_queue_name": d.get("work_queue_name"),
            "schedules": d.get("schedules", []),
            "description": d.get("description"),
            "parameter_openapi_schema": d.get("parameter_openapi_schema"),
            "path": d.get("path"),
            "entrypoint": d.get("entrypoint"),
        }


@mcp.tool(
    description=(
        "Trigger a new Prefect flow run from a deployment, optionally passing custom parameters. "
        "Parameters must match the deployment's parameter schema. "
        "Returns the new flow run ID and its initial state."
    )
)
async def prefect_trigger_flow_run(
    deployment_id: Annotated[str, Field(description="UUID of the deployment to run.")],
    parameters: Annotated[
        dict | None,
        Field(description="Key/value parameters to pass to the flow run. Must match the deployment's parameter schema."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(description="Optional list of tags to attach to the new flow run."),
    ] = None,
    idempotency_key: Annotated[
        str | None,
        Field(description="Optional idempotency key — prevents duplicate runs if the same key is submitted twice."),
    ] = None,
) -> dict:
    async with trace_tool("prefect_trigger_flow_run", inputs={"deployment_id": deployment_id, "has_params": bool(parameters)}):
        body: dict = {"parameters": parameters or {}}
        if tags:
            body["tags"] = tags
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        async with get_prefect_client() as client:
            response = await client.post(f"deployments/{deployment_id}/create_flow_run", json=body)
            await raise_for_status(response)
            run = response.json()

        return {
            "flow_run_id": run["id"],
            "name": run.get("name"),
            "state_type": run.get("state_type"),
            "state_name": run.get("state_name"),
            "expected_start_time": run.get("expected_start_time"),
        }
