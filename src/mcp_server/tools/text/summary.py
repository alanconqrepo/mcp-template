from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.text import truncate, word_count


@mcp.tool(description="Returns a short summary of the provided text content.")
async def text_summary(content: str, max_length: int = 200) -> dict:
    """Truncates content to max_length and returns word count metadata."""
    async with trace_tool("text_summary", inputs={"content_length": len(content), "max_length": max_length}):
        original_length = len(content)
        wc = word_count(content)
        summary = truncate(content, max_length)
        return {
            "summary": summary,
            "original_length": original_length,
            "word_count": wc,
            "truncated": len(content) > max_length,
        }
