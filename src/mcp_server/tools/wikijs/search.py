from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.wikijs_client import graphql

_SEARCH_QUERY = """
query($query: String!, $locale: String) {
  pages {
    search(query: $query, locale: $locale) {
      results {
        id
        title
        description
        path
        locale
      }
    }
  }
}
"""


@mcp.tool(description="Search Wiki.js pages by keyword. Returns matching pages with their id, title, description and path.")
async def wikijs_search_pages(
    query: Annotated[str, Field(description="Search keywords")],
    locale: Annotated[str, Field(description="Locale code to search in, e.g. 'en' or 'fr'")] = "en",
    limit: Annotated[int, Field(description="Maximum number of results to return", ge=1, le=100)] = 25,
) -> dict:
    async with trace_tool("wikijs_search_pages", inputs={"query": query, "locale": locale, "limit": limit}):
        data = await graphql(_SEARCH_QUERY, {"query": query, "locale": locale})
        results = data.get("pages", {}).get("search", {}).get("results", [])
        return {"results": results[:limit], "total": len(results[:limit])}
