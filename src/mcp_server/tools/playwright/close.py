from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.tools.playwright.session import close_session


@mcp.tool(
    description=(
        "Close the current browser session and free its resources. "
        "The next browser_navigate call will open a fresh session automatically."
    )
)
async def browser_close() -> dict:
    async with trace_tool("browser_close"):
        await close_session()
        return {"success": True}
