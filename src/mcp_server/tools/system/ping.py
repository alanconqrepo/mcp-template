from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.datetime import iso_now


@mcp.tool(description="Returns pong. Use this to test connectivity.")
async def ping() -> dict[str, str]:
    """Returns pong with a UTC timestamp."""
    async with trace_tool("ping"):
        return {"message": "pong", "timestamp": iso_now()}
