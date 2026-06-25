from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.tools.playwright.session import get_page


@mcp.tool(
    description=(
        "Navigate the browser to a URL. Returns the page title, final URL, and HTTP status. "
        "Always call this first to open a page before using other browser_* tools."
    )
)
async def browser_navigate(
    url: str,
    wait_until: str = "domcontentloaded",
    timeout: int = 30000,
) -> dict:
    """
    Args:
        url: Full URL to visit (must include https:// or http://).
        wait_until: Navigation completion signal — 'load', 'domcontentloaded', or 'networkidle'.
        timeout: Max wait time in milliseconds (default 30 000).
    """
    async with trace_tool("browser_navigate", inputs={"url": url}):
        page = await get_page()
        try:
            response = await page.goto(url, wait_until=wait_until, timeout=timeout)
            title = await page.title()
            return {
                "url": page.url,
                "title": title,
                "status": response.status if response else None,
            }
        except Exception as e:
            return {"error": str(e), "url": url}
