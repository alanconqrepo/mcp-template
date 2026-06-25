from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.tools.playwright.session import get_page


@mcp.tool(
    description=(
        "Extract the visible text content of the current page or a specific element. "
        "Prefer this over browser_screenshot when you only need to read text."
    )
)
async def browser_get_text(selector: str = "body") -> dict:
    """
    Args:
        selector: CSS selector of the element to extract text from (default: 'body' = full page).
    """
    async with trace_tool("browser_get_text"):
        page = await get_page()
        try:
            text = await page.locator(selector).first.inner_text(timeout=5000)
            return {"url": page.url, "selector": selector, "text": text}
        except Exception as e:
            return {"error": str(e)}


@mcp.tool(
    description=(
        "Get the raw HTML markup of the current page or a specific element. "
        "Use when you need to inspect DOM structure or scrape structured data."
    )
)
async def browser_get_html(selector: str = "body") -> dict:
    """
    Args:
        selector: CSS selector of the element (default: 'body' = full page body).
    """
    async with trace_tool("browser_get_html"):
        page = await get_page()
        try:
            html = await page.locator(selector).first.inner_html(timeout=5000)
            return {"url": page.url, "selector": selector, "html": html}
        except Exception as e:
            return {"error": str(e)}
