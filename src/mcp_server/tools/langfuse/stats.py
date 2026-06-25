from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from mcp_server.observability.langfuse import get_langfuse, trace_tool
from mcp_server.server import mcp


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


@mcp.tool(description="Aggregate Langfuse usage statistics: call counts per tool and per user, error count, average duration.")
async def langfuse_usage_stats(
    limit: int = 200,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
) -> dict:
    async with trace_tool("langfuse_usage_stats"):
        client = get_langfuse()
        if client is None:
            return {"error": "Langfuse not configured"}

        limit = min(limit, 500)
        response = client.fetch_traces(
            limit=limit,
            from_timestamp=_parse_dt(from_timestamp),
            to_timestamp=_parse_dt(to_timestamp),
        )
        traces = response.data

        by_tool: dict[str, int] = defaultdict(int)
        by_user: dict[str, int] = defaultdict(int)
        error_count = 0
        total_duration_ms = 0
        duration_count = 0

        for t in traces:
            name = t.name or "unknown"
            by_tool[name] += 1

            user = t.user_id or "anonymous"
            by_user[user] += 1

            if t.duration is not None:
                total_duration_ms += int(t.duration * 1000)
                duration_count += 1

            observations = getattr(t, "observations", None) or []
            if any(getattr(o, "level", None) == "ERROR" for o in observations):
                error_count += 1

        avg_duration_ms = round(total_duration_ms / duration_count) if duration_count else None

        return {
            "total_traces": len(traces),
            "by_tool": dict(sorted(by_tool.items(), key=lambda x: -x[1])),
            "by_user": dict(sorted(by_user.items(), key=lambda x: -x[1])),
            "error_count": error_count,
            "avg_duration_ms": avg_duration_ms,
        }
