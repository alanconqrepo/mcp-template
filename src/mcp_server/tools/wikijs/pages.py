from typing import Annotated, Literal

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.wikijs_client import graphql

_LIST_QUERY = """
query($orderBy: PageOrderBy, $locale: String) {
  pages {
    list(orderBy: $orderBy, locale: $locale) {
      id
      path
      locale
      title
      description
      contentType
      isPublished
      createdAt
      updatedAt
    }
  }
}
"""

_TREE_QUERY = """
query($locale: String!, $parent: Int) {
  pages {
    tree(locale: $locale, mode: ALL, parent: $parent) {
      id
      path
      title
      isFolder
      parent
      pageId
    }
  }
}
"""


@mcp.tool(description="List all Wiki.js pages. Optionally filter by locale and sort order.")
async def wikijs_list_pages(
    locale: Annotated[str | None, Field(description="Filter by locale code, e.g. 'en', 'fr'. Omit for all locales.")] = None,
    order_by: Annotated[
        Literal["CREATED", "ID", "PATH", "TITLE", "UPDATED"],
        Field(description="Sort order for the results"),
    ] = "TITLE",
) -> dict:
    async with trace_tool("wikijs_list_pages", inputs={"locale": locale, "order_by": order_by}):
        data = await graphql(_LIST_QUERY, {"orderBy": order_by, "locale": locale})
        pages = data.get("pages", {}).get("list", [])
        return {"pages": pages, "total": len(pages)}


@mcp.tool(description="Get the hierarchical page tree of Wiki.js. Useful to navigate the documentation structure.")
async def wikijs_get_page_tree(
    locale: Annotated[str, Field(description="Locale code, e.g. 'en' or 'fr'")] = "en",
    parent: Annotated[int | None, Field(description="Parent page ID to get children of. Omit for root.")] = None,
) -> dict:
    async with trace_tool("wikijs_get_page_tree", inputs={"locale": locale, "parent": parent}):
        data = await graphql(_TREE_QUERY, {"locale": locale, "parent": parent})
        tree = data.get("pages", {}).get("tree", [])
        return {"tree": tree, "total": len(tree)}
