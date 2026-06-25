from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.tools.playwright.session import get_page


@mcp.tool(
    description=(
        "Click an element on the current page. "
        "Accepts CSS selectors (e.g. '#submit'), XPath ('xpath=//button'), "
        "or visible text ('text=Sign in')."
    )
)
async def browser_click(selector: str, timeout: int = 5000) -> dict:
    """
    Args:
        selector: Element to click — CSS selector, 'xpath=...', or 'text=...'.
        timeout: Max time to wait for the element to be visible, in milliseconds.
    """
    async with trace_tool("browser_click", inputs={"selector": selector}):
        page = await get_page()
        try:
            await page.click(selector, timeout=timeout)
            return {"success": True, "url": page.url}
        except Exception as e:
            return {"error": str(e)}


@mcp.tool(
    description="Type a value into an input field or textarea on the current page."
)
async def browser_fill(selector: str, value: str, timeout: int = 5000) -> dict:
    """
    Args:
        selector: CSS selector for the input or textarea element.
        value: Text to type (replaces any existing content).
        timeout: Max time to wait for the element, in milliseconds.
    """
    async with trace_tool("browser_fill", inputs={"selector": selector}):
        page = await get_page()
        try:
            await page.fill(selector, value, timeout=timeout)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


@mcp.tool(
    description="Select an option in a <select> dropdown on the current page."
)
async def browser_select(selector: str, value: str, timeout: int = 5000) -> dict:
    """
    Args:
        selector: CSS selector for the <select> element.
        value: Option value attribute or visible label to select.
        timeout: Max time to wait for the element, in milliseconds.
    """
    async with trace_tool("browser_select", inputs={"selector": selector}):
        page = await get_page()
        try:
            selected = await page.select_option(selector, value=value, timeout=timeout)
            return {"success": True, "selected": selected}
        except Exception as e:
            return {"error": str(e)}


@mcp.tool(
    description=(
        "Wait until an element matching the selector appears on the current page. "
        "Useful after navigation or clicking when content loads asynchronously."
    )
)
async def browser_wait_for(selector: str, timeout: int = 10000) -> dict:
    """
    Args:
        selector: CSS selector to wait for.
        timeout: Max wait time in milliseconds (default 10 000).
    """
    async with trace_tool("browser_wait_for", inputs={"selector": selector}):
        page = await get_page()
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "found": selector}
        except Exception as e:
            return {"error": str(e)}
