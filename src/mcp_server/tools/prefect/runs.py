from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.prefect_client import get_prefect_client, raise_for_status


@mcp.tool(
    description=(
        "Cancel a Prefect flow run that is currently RUNNING or SCHEDULED. "
        "The run transitions to CANCELLING, then the infrastructure agent moves it to CANCELLED. "
        "Has no effect on runs that are already in a terminal state (COMPLETED, FAILED, CANCELLED)."
    )
)
async def prefect_cancel_flow_run(
    flow_run_id: Annotated[str, Field(description="UUID of the flow run to cancel.")],
) -> dict:
    async with trace_tool("prefect_cancel_flow_run", inputs={"flow_run_id": flow_run_id}):
        body = {
            "state": {"type": "CANCELLING", "name": "Cancelling"},
            "force": False,
        }

        async with get_prefect_client() as client:
            response = await client.post(f"flow_runs/{flow_run_id}/set_state", json=body)
            await raise_for_status(response)
            result = response.json()

        status = (result.get("state") or {}).get("type") or result.get("status")
        return {
            "flow_run_id": flow_run_id,
            "status": status,
            "details": result,
        }


@mcp.tool(
    description=(
        "Retry a failed or crashed Prefect flow run by creating a new run from the same deployment, "
        "reusing the original parameters. Optionally override specific parameters. "
        "The original run must have been triggered from a deployment."
    )
)
async def prefect_retry_flow_run(
    flow_run_id: Annotated[str, Field(description="UUID of the flow run to retry.")],
    parameter_overrides: Annotated[
        dict | None,
        Field(description="Parameters to override relative to the original run. Unspecified parameters are kept as-is."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(description="Optional tags for the new run. If omitted, the original run's tags are reused."),
    ] = None,
) -> dict:
    async with trace_tool("prefect_retry_flow_run", inputs={"flow_run_id": flow_run_id, "has_overrides": bool(parameter_overrides)}):
        async with get_prefect_client() as client:
            # Fetch original run to retrieve deployment_id and parameters
            run_response = await client.get(f"flow_runs/{flow_run_id}")
            await raise_for_status(run_response)
            original_run = run_response.json()

            deployment_id = original_run.get("deployment_id")
            if not deployment_id:
                return {
                    "error": (
                        "This flow run was not created from a deployment and cannot be retried with this tool. "
                        "Use prefect_trigger_flow_run to start a new run manually."
                    )
                }

            merged_params = {**(original_run.get("parameters") or {}), **(parameter_overrides or {})}
            run_tags = tags if tags is not None else (original_run.get("tags") or [])

            body: dict = {"parameters": merged_params, "tags": run_tags}

            new_run_response = await client.post(
                f"deployments/{deployment_id}/create_flow_run", json=body
            )
            await raise_for_status(new_run_response)
            new_run = new_run_response.json()

        return {
            "original_flow_run_id": flow_run_id,
            "new_flow_run_id": new_run["id"],
            "name": new_run.get("name"),
            "state_type": new_run.get("state_type"),
            "expected_start_time": new_run.get("expected_start_time"),
            "parameters": merged_params,
        }
