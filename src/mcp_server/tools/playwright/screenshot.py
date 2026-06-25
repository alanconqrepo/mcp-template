from fastmcp import Image

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.tools.playwright.session import get_page


@mcp.tool(
    description=(
        "Take a screenshot of the current browser page and return it as an image. "
        "Use this to visually inspect the page layout, read content, or verify interactions."
    )
)
async def browser_screenshot(full_page: bool = False) -> Image:
    """
    Args:
        full_page: Capture the entire scrollable page instead of just the visible viewport.
    """
    async with trace_tool("browser_screenshot"):
        page = await get_page()
        png_bytes = await page.screenshot(full_page=full_page, type="png")
        return Image(data=png_bytes, format="png")
