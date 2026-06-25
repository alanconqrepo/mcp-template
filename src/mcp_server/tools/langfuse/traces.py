from __future__ import annotations

from datetime import datetime
from typing import Any

from mcp_server.observability.langfuse import get_langfuse, trace_tool
from mcp_server.server import mcp


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _fmt_trace(t: Any) -> dict:
    duration_ms = None
    if t.duration is not None:
        duration_ms = int(t.duration * 1000)
    level = "ERROR" if any(
        getattr(o, "level", None) == "ERROR" for o in (getattr(t, "observations", None) or [])
    ) else "OK"
    return {
        "id": t.id,
        "name": t.name,
        "user_id": t.user_id,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        "duration_ms": duration_ms,
        "status": level,
    }


@mcp.tool(description="List recent Langfuse traces. Supports filtering by user, tool name, and date range.")
async def langfuse_list_traces(
    limit: int = 20,
    user_id: str | None = None,
    name: str | None = None,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
) -> dict:
    async with trace_tool("langfuse_list_traces"):
        client = get_langfuse()
        if client is None:
            return {"error": "Langfuse not configured"}

        limit = min(limit, 100)
        response = client.fetch_traces(
            limit=limit,
            user_id=user_id,
            name=name,
            from_timestamp=_parse_dt(from_timestamp),
            to_timestamp=_parse_dt(to_timestamp),
        )
        traces = [_fmt_trace(t) for t in response.data]
        return {"count": len(traces), "traces": traces}


@mcp.tool(description="Get the full detail of a Langfuse trace by its ID, including all observations/spans.")
async def langfuse_get_trace(trace_id: str) -> dict:
    async with trace_tool("langfuse_get_trace", inputs={"trace_id": trace_id}):
        client = get_langfuse()
        if client is None:
            return {"error": "Langfuse not configured"}

        response = client.fetch_trace(trace_id)
        t = response.data
        observations = []
        for o in getattr(t, "observations", []) or []:
            observations.append({
                "id": getattr(o, "id", None),
                "name": getattr(o, "name", None),
                "type": getattr(o, "type", None),
                "level": getattr(o, "level", None),
                "input": getattr(o, "input", None),
                "output": getattr(o, "output", None),
                "start_time": o.start_time.isoformat() if getattr(o, "start_time", None) else None,
                "end_time": o.end_time.isoformat() if getattr(o, "end_time", None) else None,
                "status_message": getattr(o, "status_message", None),
                "metadata": getattr(o, "metadata", None),
            })
        return {
            "id": t.id,
            "name": t.name,
            "user_id": t.user_id,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "duration_ms": int(t.duration * 1000) if t.duration is not None else None,
            "input": getattr(t, "input", None),
            "output": getattr(t, "output", None),
            "metadata": getattr(t, "metadata", None),
            "tags": getattr(t, "tags", []),
            "observations": observations,
        }
